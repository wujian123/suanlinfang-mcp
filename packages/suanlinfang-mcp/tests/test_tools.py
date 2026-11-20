import asyncio
import json

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from suanlinfang_mcp.server import mcp

BASE = "https://api.test/v1"
EXPECTED_TOOLS = [
    "generate_image",
    "get_image_task",
    "list_image_models",
    "transcribe_audio",
    "submit_transcription_task",
    "get_transcription_task",
    "synthesize_speech",
    "submit_speech_task",
    "get_speech_task",
    "list_tts_voices",
    "submit_document_task",
    "get_document_task",
]


def _tool_payload(result) -> dict:
    text = result.content[0].text
    return json.loads(text)


def test_tools_list_complete():
    async def go():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            return [tool.name for tool in tools]

    names = asyncio.run(go())
    assert names == EXPECTED_TOOLS


def test_tool_schemas_have_descriptions():
    async def go():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            return {tool.name: tool for tool in tools}

    tools = asyncio.run(go())
    for name, tool in tools.items():
        assert tool.description, f"{name} 缺少 description（LLM 发现工具的广告位）"


def test_server_instructions_present():
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools()

    asyncio.run(go())
    assert mcp.instructions and "generate_image" in mcp.instructions


def test_clamp_wait_seconds():
    from suanlinfang_mcp.server import _clamp_wait_seconds

    assert _clamp_wait_seconds(5) == 10
    assert _clamp_wait_seconds(9999) == 300
    assert _clamp_wait_seconds(120) == 120


def test_no_key_returns_guidance(monkeypatch):
    monkeypatch.delenv("SUANLINFANG_API_KEY", raising=False)

    async def go():
        async with Client(mcp) as client:
            await client.call_tool("generate_image", {"prompt": "一只橘猫"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "api-keys.html" in str(exc_info.value)


@respx.mock
def test_generate_image_end_to_end(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    submit_route = respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-e2e"}))
    respx.get(f"{BASE}/image/tasks/img-e2e").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "resultUrl": "https://oss.test/out.png", "expireAt": "2026-11-20T12:00:00Z", "seed": 7},
        )
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool("generate_image", {"prompt": "一只戴眼镜的橘猫在看书"})

    payload = _tool_payload(asyncio.run(go()))
    assert payload["status"] == "success"
    assert payload["resultUrl"] == "https://oss.test/out.png"
    assert payload["model"] == "flux2-klein"
    assert "下载转存" in payload["note"]
    submit_body = submit_route.calls.last.request.content.decode()
    assert '"model":"flux2-klein"' in submit_body
    assert respx.calls.last.request.headers["Authorization"] == "Bearer nk-e2e"


@respx.mock
def test_generate_image_edit_flow(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    ref_url = "https://cdn.test/ref.png"
    respx.get(ref_url).mock(return_value=httpx.Response(200, content=b"png-bytes"))
    respx.post(f"{BASE}/image/upload-tickets").mock(
        return_value=httpx.Response(
            200,
            json={
                "fileKey": "inference-media/upload/1024/r.png",
                "uploadUrl": "https://oss.test/upload/r.png?sig=1",
                "method": "PUT",
                "headers": {"Content-Type": "image/png"},
            },
        )
    )
    upload_route = respx.put("https://oss.test/upload/r.png").mock(return_value=httpx.Response(200))
    submit_route = respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-edit"}))
    respx.get(f"{BASE}/image/tasks/img-edit").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "resultUrl": "https://oss.test/out.png", "inputUrl": "https://oss.test/ref-view.png", "seed": 9},
        )
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(
                "generate_image",
                {"prompt": "把风衣换成白色羽绒服", "init_image_url": ref_url, "seed": 9},
            )

    payload = _tool_payload(asyncio.run(go()))
    assert payload["model"] == "qwen-image-edit-2511"
    assert payload["inputUrl"] == "https://oss.test/ref-view.png"
    assert payload["seed"] == 9
    assert upload_route.call_count == 1
    submit_body = submit_route.calls.last.request.content.decode()
    assert '"initImageKey":"inference-media/upload/1024/r.png"' in submit_body


@respx.mock
def test_generate_image_timeout_returns_taskno(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-slow"}))
    respx.get(f"{BASE}/image/tasks/img-slow").mock(
        return_value=httpx.Response(200, json={"status": "running", "totalUnits": 1, "doneUnits": 0})
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(
                "generate_image", {"prompt": "雪山下的木屋", "wait_seconds": 10}
            )

    payload = _tool_payload(asyncio.run(go()))
    assert payload["status"] == "running"
    assert payload["taskNo"] == "img-slow"
    assert "get_image_task" in payload["hint"]


@respx.mock
def test_generate_image_failed_raises_tool_error(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-bad"}))
    respx.get(f"{BASE}/image/tasks/img-bad").mock(
        return_value=httpx.Response(200, json={"status": "failed", "errorMsg": "模型节点异常退出"})
    )

    async def go():
        async with Client(mcp) as client:
            await client.call_tool("generate_image", {"prompt": "一只橘猫"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "模型节点异常退出" in str(exc_info.value)
    assert "不扣费" in str(exc_info.value)


@respx.mock
def test_get_image_task_and_list_models(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    respx.get(f"{BASE}/image/tasks/img-q").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "resultUrl": "https://oss.test/out.png", "expireAt": "2026-11-20T12:00:00Z"},
        )
    )
    models_route = respx.get(f"{BASE}/image/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "flux2-klein", "pricing": {"unit": "image", "price": 0.10}}]})
    )

    async def go():
        async with Client(mcp) as client:
            task = await client.call_tool("get_image_task", {"task_no": "img-q"})
            models = await client.call_tool("list_image_models", {})
            return task, models

    task_payload, models_payload = asyncio.run(go())
    assert _tool_payload(task_payload)["resultUrl"] == "https://oss.test/out.png"
    assert _tool_payload(models_payload)[0]["id"] == "flux2-klein"
    assert models_route.call_count == 1



@respx.mock
def test_transcribe_audio_tool_end_to_end(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    respx.post(f"{BASE}/stt/url").mock(
        return_value=httpx.Response(
            200,
            json={
                "inferenceId": "inf-stt",
                "result": {"text": "今天的会议纪要内容。"},
                "audioInfo": {"durationMs": 9200},
            },
        )
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(
                "transcribe_audio",
                {"audio_url": "https://cdn.test/a.wav", "language": "zh", "hotwords": "王建国"},
            )

    payload = _tool_payload(asyncio.run(go()))
    assert payload["text"] == "今天的会议纪要内容。"
    assert payload["durationMs"] == 9200


@respx.mock
def test_api_error_surfaces_as_tool_error(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    respx.post(f"{BASE}/image/tasks").mock(
        return_value=httpx.Response(
            402,
            json={
                "error": {"code": "40201", "type": "insufficient_balance", "message": "账户余额不足，请充值后重试"},
                "requestId": "req-2",
            },
        )
    )

    async def go():
        async with Client(mcp) as client:
            await client.call_tool("generate_image", {"prompt": "一只橘猫"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "余额不足" in str(exc_info.value)
