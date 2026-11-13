import asyncio
import json

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from suanlinfang_mcp.server import mcp

BASE = "https://api.test/v1"
EXPECTED_TOOLS = {
    "transcribe_audio",
    "submit_transcription_task",
    "get_transcription_task",
    "synthesize_speech",
    "submit_speech_task",
    "get_speech_task",
    "list_tts_voices",
    "recognize_image",
    "submit_document_task",
    "get_document_task",
    "decide",
}


def _tool_payload(result) -> dict:
    text = result.content[0].text
    return json.loads(text)


def test_tools_list_complete():
    async def go():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            return {tool.name for tool in tools}

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


def test_no_key_returns_guidance(monkeypatch):
    monkeypatch.delenv("SUANLINFANG_API_KEY", raising=False)

    async def go():
        async with Client(mcp) as client:
            await client.call_tool("decide", {"state": "s", "questions": {"q1": {"type": "noul"}}})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "api-keys.html" in str(exc_info.value)


@respx.mock
def test_decide_tool_end_to_end(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    respx.post(f"{BASE}/systemone").mock(
        return_value=httpx.Response(
            200,
            json={
                "inferenceId": "inf-e2e",
                "answers": {"urgent": {"type": "noul", "noul": 0.73}},
                "usage": {"input_tokens": 52, "output_tokens": 0},
            },
        )
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(
                "decide",
                {
                    "state": "订单延迟三天，外包装压坏。",
                    "questions": {"urgent": {"type": "noul", "instructions": "需要紧急介入吗？"}},
                },
            )

    payload = _tool_payload(asyncio.run(go()))
    assert payload["answers"]["urgent"]["noul"] == 0.73
    assert respx.calls.last.request.headers["Authorization"] == "Bearer nk-e2e"


@respx.mock
def test_decide_questions_object_regression(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    questions = {"team": {"type": "choice", "criteria": {"refund": "退款", "logistics": "物流"}}}
    respx.post(f"{BASE}/systemone").mock(
        return_value=httpx.Response(
            200,
            json={
                "inferenceId": "inf-obj",
                "answers": {"team": {"type": "choice", "choice": "refund"}},
                "usage": {"input_tokens": 40, "output_tokens": 0},
            },
        )
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool("decide", {"state": "外包装压坏", "questions": questions})

    payload = _tool_payload(asyncio.run(go()))
    assert payload["answers"]["team"]["choice"] == "refund"
    assert json.loads(respx.calls.last.request.content)["questions"] == questions


@respx.mock
def test_decide_questions_json_parsed_to_dict(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    questions = {"urgent": {"type": "noul", "instructions": "需要紧急介入吗？"}}
    respx.post(f"{BASE}/systemone").mock(
        return_value=httpx.Response(
            200,
            json={
                "inferenceId": "inf-json",
                "answers": {"urgent": {"type": "noul", "noul": 0.88}},
                "usage": {"input_tokens": 30, "output_tokens": 0},
            },
        )
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(
                "decide", {"state": "订单延迟三天", "questions_json": json.dumps(questions)}
            )

    payload = _tool_payload(asyncio.run(go()))
    assert payload["answers"]["urgent"]["noul"] == 0.88
    assert json.loads(respx.calls.last.request.content)["questions"] == questions


def test_decide_questions_and_json_both_missing(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")

    async def go():
        async with Client(mcp) as client:
            await client.call_tool("decide", {"state": "订单延迟三天"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "二选一必填" in str(exc_info.value)


def test_decide_questions_and_json_both_given(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")

    async def go():
        async with Client(mcp) as client:
            await client.call_tool(
                "decide",
                {
                    "state": "订单延迟三天",
                    "questions": {"urgent": {"type": "noul"}},
                    "questions_json": '{"urgent": {"type": "noul"}}',
                },
            )

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "只传其一" in str(exc_info.value)


@pytest.mark.parametrize("questions_json", ["not-json", "[1, 2]"])
def test_decide_questions_json_invalid(monkeypatch, questions_json):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")

    async def go():
        async with Client(mcp) as client:
            await client.call_tool("decide", {"state": "订单延迟三天", "questions_json": questions_json})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "questions_json" in str(exc_info.value)


def test_decide_state_non_string_rejected_by_schema(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")

    async def go():
        async with Client(mcp) as client:
            await client.call_tool("decide", {"state": 123, "questions_json": '{"urgent": {"type": "noul"}}'})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "state" in str(exc_info.value)


@respx.mock
def test_decide_questions_with_empty_json_string(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    questions = {"urgent": {"type": "noul"}}
    respx.post(f"{BASE}/systemone").mock(
        return_value=httpx.Response(
            200,
            json={
                "inferenceId": "inf-empty-str",
                "answers": {"urgent": {"type": "noul", "noul": 0.61}},
                "usage": {"input_tokens": 20, "output_tokens": 0},
            },
        )
    )

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool("decide", {"state": "订单延迟三天", "questions": questions, "questions_json": ""})

    payload = _tool_payload(asyncio.run(go()))
    assert payload["answers"]["urgent"]["noul"] == 0.61
    assert json.loads(respx.calls.last.request.content)["questions"] == questions


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
                {"audio_url": "https://cdn.test/a.wav", "language": "zh", "context": "王建国"},
            )

    payload = _tool_payload(asyncio.run(go()))
    assert payload["text"] == "今天的会议纪要内容。"
    assert payload["durationMs"] == 9200


@respx.mock
def test_api_error_surfaces_as_tool_error(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-e2e")
    monkeypatch.setenv("SUANLINFANG_BASE_URL", BASE)
    respx.post(f"{BASE}/systemone").mock(
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
            await client.call_tool("decide", {"state": "s", "questions": {}})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "余额不足" in str(exc_info.value)
