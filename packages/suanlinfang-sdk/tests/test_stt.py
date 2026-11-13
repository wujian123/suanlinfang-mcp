import httpx
import respx

from suanlinfang import SuanlinfangClient

BASE = "https://api.test/v1"


def _client() -> SuanlinfangClient:
    return SuanlinfangClient(api_key="nk-test-key", base_url=BASE)


@respx.mock
def test_transcribe_url_single():
    route = respx.post(f"{BASE}/stt/url").mock(
        return_value=httpx.Response(
            200,
            json={
                "inferenceId": "inf-1",
                "result": {"text": "欢迎来到算邻坊。"},
                "audioInfo": {"durationMs": 7400},
            },
        )
    )
    with _client() as client:
        result = client.stt.transcribe_url("https://cdn.test/a.wav", language="zh", context="王建国")
    assert result.text == "欢迎来到算邻坊。"
    assert result.duration_ms == 7400
    # 回归：表单请求的 Content-Type 必须是 urlencoded（曾因写死 application/json 假绿）
    assert route.calls.last.request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    body = route.calls.last.request.content.decode()
    assert "url=https%3A%2F%2Fcdn.test%2Fa.wav" in body
    assert "language=zh" in body
    assert "%E7%8E%8B%E5%BB%BA%E5%9B%BD" in body  # context 热词已 urlencode


@respx.mock
def test_transcribe_url_to_task_full_flow():
    audio_url = "https://cdn.test/meeting.wav"
    respx.get(audio_url).mock(return_value=httpx.Response(200, content=b"RIFF-bytes"))
    respx.post(f"{BASE}/stt/upload-tickets").mock(
        return_value=httpx.Response(
            200,
            json={
                "fileKey": "inference-media/upload/1024/t.wav",
                "uploadUrl": "https://oss.test/upload/t.wav?sig=1",
                "method": "PUT",
                "headers": {"Content-Type": "audio/wav"},
            },
        )
    )
    put_route = respx.put("https://oss.test/upload/t.wav").mock(return_value=httpx.Response(200))
    respx.post(f"{BASE}/stt/tasks").mock(
        return_value=httpx.Response(200, json={"taskId": "task-1"})
    )
    with _client() as client:
        task_no = client.stt.transcribe_url_to_task(audio_url, language="zh", context="江斌")
    assert task_no == "task-1"
    put_request = put_route.calls.last.request
    assert put_request.headers["Content-Type"] == "audio/wav"
    # 回归：PUT body 必须真带音频字节（曾因 content 未透传发出空对象，OSS 落 0 字节文件）
    assert put_request.content == b"RIFF-bytes"
    task_body = respx.calls.last.request.content.decode()
    assert "inference-media/upload/1024/t.wav" in task_body


@respx.mock
def test_get_task_with_result_text():
    respx.get(f"{BASE}/stt/tasks/task-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "totalUnits": 6,
                "doneUnits": 6,
                "resultUrl": "https://oss.test/result.json?sig=1",
                "expireAt": "2026-11-09T12:00:00Z",
            },
        )
    )
    respx.get("https://oss.test/result.json").mock(
        return_value=httpx.Response(200, json={"text": "全部段落的转写文本拼接…"})
    )
    with _client() as client:
        info = client.stt.get_task("task-1")
    assert info.status == "success"
    assert info.done_units == 6
    assert info.text == "全部段落的转写文本拼接…"


@respx.mock
def test_get_task_failed():
    respx.get(f"{BASE}/stt/tasks/task-2").mock(
        return_value=httpx.Response(200, json={"status": "failed", "errorMsg": "unit 3 失败"})
    )
    with _client() as client:
        info = client.stt.get_task("task-2")
    assert info.status == "failed"
    assert info.error_msg == "unit 3 失败"
    assert info.text is None
