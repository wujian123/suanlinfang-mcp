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


# ── DECISION ─────────────────────────────────────────

@respx.mock
def test_decision_decide():
    questions = {
        "team": {
            "type": "choice",
            "instructions": "这条工单该转给哪个团队？",
            "criteria": {"退换货": "退换、退款", "账务": "重复扣款"},
        }
    }
    respx.post(f"{BASE}/systemone").mock(
        return_value=httpx.Response(
            200,
            json={
                "inferenceId": "inf-d1",
                "answers": {"team": {"type": "choice", "choice": "账务", "confidence": 0.86, "probabilities": {}}},
                "usage": {"input_tokens": 214, "output_tokens": 0},
                "latency_ms": 37,
            },
        )
    )
    with _client() as client:
        result = client.decision.decide("订单延迟三天送达", questions)
    assert result.answers["team"]["choice"] == "账务"
    assert result.usage["input_tokens"] == 214
    assert result.latency_ms == 37
