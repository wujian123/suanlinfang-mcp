import httpx
import pytest
import respx

from suanlinfang import SuanlinfangClient

BASE = "https://api.test/v1"


def _client() -> SuanlinfangClient:
    return SuanlinfangClient(api_key="nk-test-key", base_url=BASE)


# ── TTS ──────────────────────────────────────────────

@respx.mock
def test_tts_synthesize():
    respx.post(f"{BASE}/tts").mock(
        return_value=httpx.Response(
            200,
            json={"inferenceId": "inf-t1", "durationMs": 3560, "url": "https://oss.test/out.mp3"},
        )
    )
    with _client() as client:
        result = client.tts.synthesize("欢迎使用算邻坊。", speaker="default", audio_format="mp3")
    assert result.url == "https://oss.test/out.mp3"
    body = respx.calls.last.request.content.decode()
    assert '"speaker":"default"' in body
    assert '"format":"mp3"' in body


@respx.mock
def test_tts_voices():
    respx.get(f"{BASE}/tts/voices").mock(
        return_value=httpx.Response(
            200,
            json={"voices": [{"code": "default", "displayName": "默认音色", "gender": "female", "styleTag": ""}]},
        )
    )
    with _client() as client:
        voices = client.tts.list_voices()
    assert voices[0]["code"] == "default"


@respx.mock
def test_tts_task_roundtrip():
    respx.post(f"{BASE}/tts/tasks").mock(return_value=httpx.Response(200, json={"taskId": "tts-task-1"}))
    respx.get(f"{BASE}/tts/tasks/tts-task-1").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "totalUnits": 12, "doneUnits": 12, "resultUrl": "https://oss.test/full.wav", "durationSec": 356},
        )
    )
    with _client() as client:
        task_no = client.tts.submit_task("长文本…", speaker="default")
        info = client.tts.get_task(task_no)
    assert info.status == "success"
    assert info.result_url == "https://oss.test/full.wav"


# ── OCR ──────────────────────────────────────────────

@respx.mock
def test_ocr_recognize_url():
    respx.post(f"{BASE}/ocr/url").mock(
        return_value=httpx.Response(
            200,
            json={
                "logId": "log-1",
                "wordsResultNum": 2,
                "wordsResult": [{"words": "算邻坊 GPU 算力共享平台"}, {"words": "闲置算力 · 共享收益"}],
            },
        )
    )
    with _client() as client:
        result = client.ocr.recognize_url("https://cdn.test/doc.png", tier="accurate", prompt="只提取表格金额列")
    assert result.words == ["算邻坊 GPU 算力共享平台", "闲置算力 · 共享收益"]
    body = respx.calls.last.request.content.decode()
    assert "tier=accurate" in body


@respx.mock
def test_ocr_pdf_from_url_flow():
    pdf_url = "https://cdn.test/contract.pdf"
    respx.get(pdf_url).mock(return_value=httpx.Response(200, content=b"%PDF-1.4 bytes"))
    respx.post(f"{BASE}/ocr/upload-tickets").mock(
        return_value=httpx.Response(
            200,
            json={
                "fileKey": "inference-media/upload/1024/c.pdf",
                "uploadUrl": "https://oss.test/upload/c.pdf?sig=1",
                "method": "PUT",
                "headers": {"Content-Type": "application/pdf"},
            },
        )
    )
    respx.put("https://oss.test/upload/c.pdf").mock(return_value=httpx.Response(200))
    respx.post(f"{BASE}/ocr/tasks").mock(return_value=httpx.Response(200, json={"taskId": "ocr-task-1"}))
    with _client() as client:
        task_no = client.ocr.submit_pdf_from_url(pdf_url, tier="accurate", prompt="识别发票金额")
    assert task_no == "ocr-task-1"
    task_body = respx.calls.last.request.content.decode()
    assert "inference-media/upload/1024/c.pdf" in task_body
    assert '"tier":"accurate"' in task_body


def test_ocr_pdf_rejects_non_pdf():
    with _client() as client:
        with pytest.raises(ValueError):
            client.ocr.submit_pdf_from_url("https://cdn.test/doc.png", tier="standard")


# ── IMAGE ────────────────────────────────────────────

@respx.mock
def test_image_models():
    respx.get(f"{BASE}/image/models").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "flux2-klein", "pricing": {"unit": "image", "price": 0.10}}]},
        )
    )
    with _client() as client:
        models = client.image.list_models()
    assert models[0]["id"] == "flux2-klein"


@respx.mock
def test_image_task_roundtrip():
    route = respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-task-1"}))
    respx.get(f"{BASE}/image/tasks/img-task-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "totalUnits": 1,
                "doneUnits": 1,
                "resultUrl": "https://oss.test/out.png",
                "inputUrl": "https://oss.test/ref.png",
                "expireAt": "2026-11-20T12:00:00Z",
                "seed": 42,
            },
        )
    )
    with _client() as client:
        task_no = client.image.submit_task(
            "qwen-image-edit-2511", "换成白色羽绒服", init_image_key="inference-media/upload/1024/r.png", seed=42
        )
        info = client.image.get_task(task_no)
    assert task_no == "img-task-1"
    submit_body = route.calls.last.request.content.decode()
    assert '"model":"qwen-image-edit-2511"' in submit_body
    assert '"initImageKey":"inference-media/upload/1024/r.png"' in submit_body
    assert '"seed":42' in submit_body
    assert info.status == "success"
    assert info.result_url == "https://oss.test/out.png"
    assert info.input_url == "https://oss.test/ref.png"
    assert info.seed == 42


@respx.mock
def test_image_generate_default_text_model(monkeypatch):
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    route = respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-gen-1"}))
    respx.get(f"{BASE}/image/tasks/img-gen-1").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "resultUrl": "https://oss.test/out.png", "expireAt": "2026-11-20T12:00:00Z", "seed": 7},
        )
    )
    with _client() as client:
        result = client.image.generate_image("一只戴眼镜的橘猫在看书")
    assert result.completed is True
    assert result.status == "success"
    assert result.model == "flux2-klein"
    assert result.result_url == "https://oss.test/out.png"
    submit_body = route.calls.last.request.content.decode()
    assert '"model":"flux2-klein"' in submit_body
    assert "initImageKey" not in submit_body


@respx.mock
def test_image_generate_default_edit_model(monkeypatch):
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
    submit_route = respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-edit-1"}))
    respx.get(f"{BASE}/image/tasks/img-edit-1").mock(
        return_value=httpx.Response(200, json={"status": "success", "resultUrl": "https://oss.test/out.png", "seed": 9})
    )
    with _client() as client:
        result = client.image.generate_image("把风衣换成白色羽绒服", init_image_url=ref_url)
    assert result.model == "qwen-image-edit-2511"
    assert result.completed is True
    assert upload_route.call_count == 1
    submit_body = submit_route.calls.last.request.content.decode()
    assert '"initImageKey":"inference-media/upload/1024/r.png"' in submit_body


@respx.mock
def test_image_generate_timeout_degrades(monkeypatch):
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-slow-1"}))
    respx.get(f"{BASE}/image/tasks/img-slow-1").mock(
        return_value=httpx.Response(200, json={"status": "running", "totalUnits": 1, "doneUnits": 0})
    )
    with _client() as client:
        result = client.image.generate_image("雪山下的木屋", wait_seconds=10)
    assert result.completed is False
    assert result.status == "running"
    assert result.task_no == "img-slow-1"


@respx.mock
def test_image_generate_failed_returns_status(monkeypatch):
    monkeypatch.setattr("suanlinfang.http._sleep", lambda seconds: None)
    respx.post(f"{BASE}/image/tasks").mock(return_value=httpx.Response(200, json={"taskId": "img-bad-1"}))
    respx.get(f"{BASE}/image/tasks/img-bad-1").mock(
        return_value=httpx.Response(200, json={"status": "failed", "errorMsg": "参考图分辨率过低"})
    )
    with _client() as client:
        result = client.image.generate_image("把风衣换成白色羽绒服", model="qwen-image-edit-2511")
    assert result.completed is True
    assert result.status == "failed"
    assert result.error_msg == "参考图分辨率过低"


def test_image_upload_rejects_bad_extension():
    with _client() as client:
        with pytest.raises(ValueError):
            client.image.upload_init_image("https://cdn.test/anim.gif")
