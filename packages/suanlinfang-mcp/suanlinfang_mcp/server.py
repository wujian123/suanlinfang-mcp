import asyncio
import re
from typing import Any, Literal

import anyio
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import CLIENT_INFO_META_KEY, ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from suanlinfang import SuanlinfangApiError, SuanlinfangClient
from suanlinfang_mcp.auth import resolve_api_key

try:
    from fastmcp.server.dependencies import get_context
except ImportError:
    get_context = None

SERVER_INSTRUCTIONS = (
    "算邻坊 AI 能力（suanlinfang.cn，按量计费，失败不计费）。"
    "生图为引流主推能力：generate_image 一次调用出图（文生图/图生图合一，默认自动选模型）。"
    "另有语音识别（STT）、语音合成（TTS）、文字识别（OCR）三族能力。"
    "所有工具调用需 API Key（nk- 前缀，suanlinfang.cn/consume-web/api-keys.html 创建，新用户赠 ¥10 体验金）。"
)

WAIT_SECONDS_DEFAULT = 120
WAIT_SECONDS_MIN = 10
WAIT_SECONDS_MAX = 300

mcp = FastMCP("suanlinfang", instructions=SERVER_INSTRUCTIONS)

POLL_HINT = "建议每 10~30 秒查询一次（长音频按音频时长的 1/6~1/4 估算总耗时）"

# 工具注解（MCP 协议 hints）：只读工具客户端可免确认直调；计费操作标非幂等，提醒 agent 重试会重复计费
_READ_ONLY = ToolAnnotations(read_only_hint=True)
_BILLED_ACTION = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False)


def _client() -> SuanlinfangClient:
    return SuanlinfangClient(api_key=resolve_api_key(), client_tag=_client_tag())


def _client_tag() -> str:
    """渠道归因：能取到客户端名 → mcp-<客户端名>（如 mcp-cursor）；取不到也兜底裸值 mcp
    ——经本 server 发出的请求必然是 MCP 流量，身份已知，细目（哪个客户端）才是可选增强。
    客户端名两个协议纪元二选一：2026-07-28+ 随每请求 _meta 携带，此前在 initialize 握手顶层。"""
    name = _client_name()
    normalized = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    if normalized:
        return ("mcp-" + normalized)[:32]
    return "mcp"


def _client_name() -> str | None:
    context = _current_context()
    if context is None:
        return None
    try:
        request_context = context.request_context
        # 新纪元：clientInfo 随每请求 _meta（dict 形态）
        meta_info = request_context.meta.get(CLIENT_INFO_META_KEY)
        if isinstance(meta_info, dict) and meta_info.get("name"):
            return str(meta_info["name"])
        # 经典纪元：initialize 握手顶层（对象形态）
        client_info = request_context.session.client_params.clientInfo
        return (client_info.name if client_info else None)
    except Exception:
        return None


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "suanlinfang-mcp"})


def _clamp_wait_seconds(value: int) -> int:
    return max(WAIT_SECONDS_MIN, min(value, WAIT_SECONDS_MAX))


def _current_context():
    """请求上下文（无 fastmcp 依赖或无请求上下文时返回 None）。"""
    if get_context is None:
        return None
    try:
        return get_context()
    except Exception:
        return None


def _make_progress_reporter(context, loop: asyncio.AbstractEventLoop):
    """SDK 轮询跑在工作线程；progress notification 是协程，须回投主事件循环。"""

    def on_progress(status: str, elapsed_seconds: float, wait_seconds: float) -> None:
        try:
            for coroutine in (
                context.report_progress(int(elapsed_seconds), int(wait_seconds)),
                context.info(f"生图任务 {status}（已等待 {int(elapsed_seconds)} 秒）"),
            ):
                future = asyncio.run_coroutine_threadsafe(coroutine, loop)
                # 取走异常避免「exception was never retrieved」噪音
                future.add_done_callback(lambda f: f.exception())
        except Exception:
            return

    return on_progress


@mcp.tool(annotations=_BILLED_ACTION)
async def generate_image(
    prompt: str,
    model: str | None = None,
    init_image_url: str | None = None,
    seed: int | None = None,
    wait_seconds: int = WAIT_SECONDS_DEFAULT,
) -> dict:
    """AI 生图（1024×1024 PNG，按张计费，失败不计费）：传 prompt 即文生图；再传 init_image_url（参考图公网 URL，png/jpg/jpeg ≤10MB）即图生图（换装/换景/改背景等编辑指令写在 prompt 里）。
    本工具一次调用内完成「提交→等待→出结果」，默认最多等 120 秒（wait_seconds 可调 10~300）；
    出图成功返回 resultUrl（现签下载链接，1 小时内有效，请提醒用户及时下载转存）。
    model 留空自动选：文生图=flux2-klein（快而省），图生图=qwen-image-edit-2511；要更高质量可传 z-image-turbo，在线模型与实时牌价先用 list_image_models 查询。
    seed（非负整数）可复现同图：同 prompt + 同 seed 生成一致结果。
    若等待超时仍未完成，返回 taskNo（任务不丢失、不计排队费），调用 get_image_task 继续查询。"""
    wait = _clamp_wait_seconds(wait_seconds)
    context = _current_context()
    on_progress = _make_progress_reporter(context, asyncio.get_running_loop()) if context else None

    def run() -> Any:
        with _client() as client:
            return client.image.generate_image(
                prompt,
                model=model,
                init_image_url=init_image_url,
                seed=seed,
                wait_seconds=wait,
                on_progress=on_progress,
            )

    result = await anyio.to_thread.run_sync(run)
    if result.status in ("failed", "expired"):
        raise ToolError(f"生图任务失败：{result.error_msg or '未知原因'}（失败不扣费，可调整 prompt/参考图后重试）")
    payload: dict[str, Any] = {
        "status": result.status,
        "taskNo": result.task_no,
        "model": result.model,
    }
    if result.result_url:
        payload["resultUrl"] = result.result_url
        payload["note"] = "下载链接 1 小时内有效，请提醒用户及时下载转存"
    if result.input_url:
        payload["inputUrl"] = result.input_url
    if result.expire_at:
        payload["expireAt"] = result.expire_at
    if result.seed is not None:
        payload["seed"] = result.seed
    if not result.completed:
        payload["hint"] = f"仍在生成（已等待 {wait} 秒，任务不丢失），请调用 get_image_task 继续查询"
    return payload


@mcp.tool(annotations=_READ_ONLY)
def get_image_task(task_no: str) -> dict:
    """查询生图任务状态。status：queued/running（进行中，快档常在数十秒内出图，慢档可能数分钟——视模型档位与当前空闲算力）、
    success（resultUrl 为图片现签下载链接，1 小时内有效；链接过期后重新查询即换新链）、
    failed（errorMsg 为失败原因，不扣费）、expired（结果已过保留期）。
    建议每 5~10 秒查询一次。generate_image 等待超时降级后用本工具续查。"""
    with _client() as client:
        info = client.image.get_task(task_no)
    payload: dict[str, Any] = {"status": info.status}
    if info.result_url:
        payload["resultUrl"] = info.result_url
    if info.input_url:
        payload["inputUrl"] = info.input_url
    if info.expire_at:
        payload["expireAt"] = info.expire_at
    if info.error_msg:
        payload["errorMsg"] = info.error_msg
    return payload


@mcp.tool(annotations=_READ_ONLY)
def list_image_models() -> list[dict]:
    """查询生图当前在线模型与实时牌价（id + pricing，按张计费）。选 model 前先看这个。"""
    with _client() as client:
        return client.image.list_models()


@mcp.tool(annotations=_BILLED_ACTION)
def transcribe_audio(audio_url: str, language: str | None = None, hotwords: str | None = None) -> dict:
    """把一段短音频（公网 URL）转成文字。适用于 ≤3 分钟、≤20MB 的录音/语音消息，同步秒级返回。
    更长的音频请改用 submit_transcription_task（异步任务）。
    language 留空自动检测（支持普通话、英语及 22 种中文方言）；指定时用语种代码（如 zh、en）。
    hotwords 可传热词（人名、术语、品牌，逗号分隔），专有名词按所列写法优先转写——会议转写建议填与会人名。
    返回全文纯文本（不含时间戳/分句时间轴）。计费按音频实际时长（约 0.5 元/小时，精确到秒），失败不计费。"""
    with _client() as client:
        result = client.stt.transcribe_url(audio_url, language=language, hotwords=hotwords)
        return {
            "text": result.text,
            "durationMs": result.duration_ms,
            "inferenceId": result.inference_id,
        }


@mcp.tool(annotations=_BILLED_ACTION)
def submit_transcription_task(
    audio_url: str,
    language: str | None = None,
    hotwords: str | None = None,
    file_name: str | None = None,
) -> dict:
    """提交长音频转写任务（会议录音/播客/网课，最长 2 小时、≤500MB，wav/mp3/flac/m4a/ogg/aac）。
    平台自动按 180 秒切段逐段转写并拼接全文（纯文本，不含时间戳）。提交后用 get_transcription_task 轮询结果。
    language 留空自动检测，指定时用语种代码（如 zh、en）；hotwords 可传热词（人名、术语、品牌，逗号分隔），对全部音频段生效。
    计费按实际时长（约 0.5 元/小时），余额不足会在提交时被拒绝。"""
    with _client() as client:
        task_no = client.stt.transcribe_url_to_task(
            audio_url, language=language, hotwords=hotwords, file_name=file_name
        )
        return {"taskNo": task_no, "hint": POLL_HINT}


@mcp.tool(annotations=_READ_ONLY)
def get_transcription_task(task_no: str) -> dict:
    """查询长音频转写任务状态。status：queued/running（进行中，看 doneUnits/totalUnits 进度）、
    success（text 为全文转写）、failed（errorMsg 为失败原因）。任务终态保留 72 小时。"""
    with _client() as client:
        info = client.stt.get_task(task_no)
        payload: dict[str, Any] = {
            "status": info.status,
            "totalUnits": info.total_units,
            "doneUnits": info.done_units,
        }
        if info.text is not None:
            payload["text"] = info.text
        if info.result_url:
            payload["resultUrl"] = info.result_url
        if info.error_msg:
            payload["errorMsg"] = info.error_msg
        return payload


@mcp.tool(annotations=_BILLED_ACTION)
def synthesize_speech(text: str, speaker: str = "default", audio_format: Literal["wav", "mp3"] = "wav") -> dict:
    """把文本合成为语音（≤1000 字符），同步返回现签下载链接（url，GET 即得音频，1 小时内有效）。
    请提醒用户及时下载转存——链接过期后只能重新合成（重复计费）。
    更长的文本请改用 submit_speech_task（异步任务）。speaker 音色代码先用 list_tts_voices 查询。
    计费约 2 元/万字符，失败不计费。"""
    with _client() as client:
        result = client.tts.synthesize(text, speaker=speaker, audio_format=audio_format)
        return {
            "url": result.url,
            "durationMs": result.duration_ms,
            "inferenceId": result.inference_id,
        }


@mcp.tool(annotations=_BILLED_ACTION)
def submit_speech_task(
    text: str, speaker: str = "default", audio_format: Literal["wav", "mp3"] = "wav"
) -> dict:
    """提交长文本语音合成任务（≤20 万字）：平台按 500 字切块合成并拼接为完整音频。
    提交后用 get_speech_task 轮询结果。计费约 2 元/万字符。"""
    with _client() as client:
        task_no = client.tts.submit_task(text, speaker=speaker, audio_format=audio_format)
        return {"taskNo": task_no, "hint": POLL_HINT}


@mcp.tool(annotations=_READ_ONLY)
def get_speech_task(task_no: str) -> dict:
    """查询长文本语音合成任务状态。status：queued/running（看 doneUnits/totalUnits）、
    success（resultUrl 为完整音频下载链接，1 小时内有效，过期重查即换新链）、failed（errorMsg）。
    任务终态保留 72 小时。"""
    with _client() as client:
        info = client.tts.get_task(task_no)
        payload: dict[str, Any] = {
            "status": info.status,
            "totalUnits": info.total_units,
            "doneUnits": info.done_units,
        }
        if info.result_url:
            payload["resultUrl"] = info.result_url
        if info.error_msg:
            payload["errorMsg"] = info.error_msg
        return payload


@mcp.tool(annotations=_READ_ONLY)
def list_tts_voices() -> list[dict]:
    """查询语音合成当前可用音色清单（code/name/gender/styleTag）。合成前先看这个选 speaker。"""
    with _client() as client:
        return client.tts.list_voices()


@mcp.tool(annotations=_BILLED_ACTION)
def submit_document_task(
    document_url: str,
    tier: Literal["standard", "accurate"],
    prompt: str | None = None,
    file_name: str | None = None,
) -> dict:
    """提交 PDF 文档识别任务（≤200MB、≤500 页，逐页识别整本）。适合扫描合同/书籍/报告。
    提交后用 get_document_task 轮询结果。prompt 仅精准档生效。计费按页。"""
    with _client() as client:
        task_no = client.ocr.submit_pdf_from_url(document_url, tier=tier, prompt=prompt, file_name=file_name)
        return {"taskNo": task_no, "hint": POLL_HINT}


@mcp.tool(annotations=_READ_ONLY)
def get_document_task(task_no: str) -> dict:
    """查询 PDF 文档识别任务状态。status：queued/running（看 doneUnits/totalUnits 进度）、
    success（resultUrl 为聚合结果下载链接）、failed（errorMsg）。任务终态保留 72 小时。"""
    with _client() as client:
        info = client.ocr.get_task(task_no)
        payload: dict[str, Any] = {
            "status": info.status,
            "totalUnits": info.total_units,
            "doneUnits": info.done_units,
        }
        if info.result_url:
            payload["resultUrl"] = info.result_url
        if info.error_msg:
            payload["errorMsg"] = info.error_msg
        return payload


__all__ = ["mcp", "SuanlinfangApiError", "ToolError"]
