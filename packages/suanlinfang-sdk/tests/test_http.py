import httpx
import pytest
import respx

from suanlinfang import SuanlinfangApiError, SuanlinfangClient

BASE = "https://api.test/v1"


def _client() -> SuanlinfangClient:
    return SuanlinfangClient(api_key="nk-test-key", base_url=BASE)


@respx.mock
def test_auth_header_sent():
    route = respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "t1"}))
    with _client() as client:
        client.image.submit_task("flux2-klein", "一只橘猫")
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer nk-test-key"


@respx.mock
def test_error_envelope_mapping():
    respx.post(f"{BASE}/image/tasks").mock(
        return_value=httpx.Response(
            402,
            json={
                "error": {"code": "40201", "type": "insufficient_balance", "message": "账户余额不足，请充值后重试"},
                "requestId": "req-1",
            },
        )
    )
    with _client() as client:
        with pytest.raises(SuanlinfangApiError) as exc_info:
            client.image.submit_task("flux2-klein", "一只橘猫")
    error = exc_info.value
    assert error.status_code == 402
    assert error.code == "40201"
    assert error.error_type == "insufficient_balance"
    assert error.request_id == "req-1"
    assert not error.retryable
    assert "40201" in str(error)


@respx.mock
def test_503_retry_with_retry_after(monkeypatch):
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    route = respx.post(f"{BASE}/image/tasks").mock(
        side_effect=[
            httpx.Response(503, headers={"Retry-After": "1"}, json={}),
            httpx.Response(200, json={"taskId": "t1"}),
        ]
    )
    with _client() as client:
        task_no = client.image.submit_task("flux2-klein", "一只橘猫")
    assert task_no == "t1"
    assert route.call_count == 2


@respx.mock
def test_503_retries_exhausted(monkeypatch):
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    route = respx.post(f"{BASE}/image/tasks").mock(
        return_value=httpx.Response(503, json={"error": {"message": "no nodes"}})
    )
    with _client() as client:
        with pytest.raises(SuanlinfangApiError) as exc_info:
            client.image.submit_task("flux2-klein", "一只橘猫")
    assert exc_info.value.retryable
    assert route.call_count == 4  # 1 次首发 + 3 次重试


@respx.mock
def test_timeout_maps_to_retryable_504():
    respx.post(f"{BASE}/image/tasks").mock(side_effect=httpx.ReadTimeout("timed out"))
    with _client() as client:
        with pytest.raises(SuanlinfangApiError) as exc_info:
            client.image.submit_task("flux2-klein", "一只橘猫")
    error = exc_info.value
    assert error.status_code == 504
    assert error.retryable
    assert "超时" in str(error)


@respx.mock
def test_stream_to_file_size_cap(tmp_path):
    audio_url = "https://cdn.test/a.wav"
    respx.get(audio_url).mock(
        return_value=httpx.Response(200, headers={"Content-Length": "99999999999"}, content=b"x" * 10)
    )
    with _client() as client:
        with pytest.raises(SuanlinfangApiError) as exc_info:
            client.stt.transport.stream_to_file(audio_url, str(tmp_path / "a.wav"), 500 * 1024 * 1024)
    assert exc_info.value.status_code == 413
