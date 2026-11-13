import json
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from suanlinfang import SuanlinfangApiError, SuanlinfangClient
from suanlinfang_mcp.auth import resolve_api_key

mcp = FastMCP("suanlinfang")

POLL_HINT = "建议每 10~30 秒查询一次（长音频按音频时长的 1/6~1/4 估算总耗时）"

# 工具注解（MCP 协议 hints）：只读工具客户端可免确认直调；计费操作标非幂等，提醒 agent 重试会重复计费
_READ_ONLY = ToolAnnotations(read_only_hint=True)
_BILLED_ACTION = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False)


def _client() -> SuanlinfangClient:
    return SuanlinfangClient(api_key=resolve_api_key())


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "suanlinfang-mcp"})


@mcp.tool(annotations=_BILLED_ACTION)
def transcribe_audio(audio_url: str, language: str | None = None, context: str | None = None) -> dict:
    """把一段短音频（公网 URL）转成文字。适用于 ≤3 分钟、≤20MB 的录音/语音消息，同步秒级返回。
    更长的音频请改用 submit_transcription_task（异步任务）。
    language 留空自动检测（支持普通话、英语及 22 种中文方言）；指定时用语种代码（如 zh、en）。
    context 可传热词（人名、术语、品牌，逗号分隔），专有名词按所列写法优先转写——会议转写建议填与会人名。
    返回全文纯文本（不含时间戳/分句时间轴）。计费按音频实际时长（约 0.5 元/小时，精确到秒），失败不计费。"""
    with _client() as client:
        result = client.stt.transcribe_url(audio_url, language=language, context=context)
        return {
            "text": result.text,
            "durationMs": result.duration_ms,
            "inferenceId": result.inference_id,
        }


@mcp.tool(annotations=_BILLED_ACTION)
def submit_transcription_task(
    audio_url: str,
    language: str | None = None,
    context: str | None = None,
    file_name: str | None = None,
) -> dict:
    """提交长音频转写任务（会议录音/播客/网课，最长 2 小时、≤500MB，wav/mp3/flac/m4a/ogg/aac）。
    平台自动按 180 秒切段逐段转写并拼接全文（纯文本，不含时间戳）。提交后用 get_transcription_task 轮询结果。
    language 留空自动检测，指定时用语种代码（如 zh、en）；context 可传热词（人名、术语、品牌，逗号分隔），对全部音频段生效。
    计费按实际时长（约 0.5 元/小时），余额不足会在提交时被拒绝。"""
    with _client() as client:
        task_no = client.stt.transcribe_url_to_task(
            audio_url, language=language, context=context, file_name=file_name
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
    """把文本合成为语音（≤3000 UTF-8 字节，约 1000 汉字），同步返回现签下载链接（url，GET 即得音频，1 小时内有效）。
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
def recognize_image(image_url: str, tier: Literal["standard", "accurate"], prompt: str | None = None) -> dict:
    """识别图片中的文字（png/jpg/webp/bmp，≤20MB，公网 URL），同步返回逐行文本。
    tier：standard 标准档（快速，适合清晰打印件/截图）；accurate 精准档（表格、多栏、倾斜拍摄等复杂版面）。
    prompt 仅精准档生效：自定义识别指令（如「只提取表格金额列」），≤2000 字符，缺省识别全部文字。
    计费按页（单图=1 页，约 0.5~1.5 分/页）。"""
    with _client() as client:
        result = client.ocr.recognize_url(image_url, tier=tier, prompt=prompt)
        return {
            "logId": result.log_id,
            "words": result.words,
            "wordsResultNum": result.words_result_num,
        }


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


@mcp.tool(annotations=_BILLED_ACTION)
def decide(state: str, questions: dict | None = None, questions_json: str = "") -> dict:
    """智能决策（System One 类型化判断）：输入业务状态与若干类型化问题，返回每题的校准概率，不生成文本。
    适用：工单分类、风控判定、质检评估等结构化判断场景。无上下文记忆，每次请求独立。
    questions 为 {题目id: 题目} 映射（1-32 题），type 三种：choice（多选一，criteria={选项名:描述}）、
    noul（是否判断，criteria 可选 {true:描述,false:描述}）、score（有序等级打分，criteria=[等级描述...]），可选 instructions 说明该问什么。
    示例：{"team":{"type":"choice","criteria":{"refund":"退款","logistics":"物流"}},"urgent":{"type":"noul"},"severity":{"type":"score","criteria":["轻微","一般","严重"]}}
    answers 按同键回传，含选中项、置信度与全选项概率。
    计费按输入 token（约 2 元/百万，输出免费），失败不计费。
    不支持对象入参的客户端可改传 questions_json（questions 的 JSON 字符串，二选一）。

    Args:
        questions: 类型化问题映射（{题目id: 题目}，结构见上）。与 questions_json 二选一必填。
        questions_json: questions 的 JSON 字符串形式，供只支持标量参数的客户端（如扣子试运行）使用。与 questions 二选一必填。
    """
    if questions is None and not questions_json:
        raise ToolError(
            "questions 与 questions_json 二选一必填：questions 为 {题目id: 题目} 映射，"
            '示例 {"urgent": {"type": "noul"}}；'
            "不支持对象入参的客户端可传其 JSON 字符串到 questions_json。"
        )
    if questions is not None and questions_json:
        raise ToolError("questions 与 questions_json 二选一，请只传其一，不要同时传。")
    if questions_json:
        try:
            parsed = json.loads(questions_json)
        except json.JSONDecodeError as error:
            raise ToolError(f"questions_json 不是合法 JSON：{error.msg}（第 {error.lineno} 行第 {error.colno} 列）") from error
        if not isinstance(parsed, dict):
            raise ToolError("questions_json 解析结果必须是 JSON 对象（{题目id: 题目} 映射），当前不是对象。")
        questions = parsed
    with _client() as client:
        result = client.decision.decide(state, questions)
        return {
            "inferenceId": result.inference_id,
            "answers": result.answers,
            "usage": result.usage,
        }


__all__ = ["mcp", "SuanlinfangApiError", "ToolError"]
