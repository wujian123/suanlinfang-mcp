from typing import Any

from suanlinfang.http import HttpTransport
from suanlinfang.types import TaskInfo, TtsSingleResult


class TtsClient:
    def __init__(self, transport: HttpTransport):
        self.transport = transport

    def synthesize(self, text: str, speaker: str, audio_format: str | None = None) -> TtsSingleResult:
        """单笔合成（≤1000 字符），同步返回现签下载链接（1 小时有效）。"""
        audio_params: dict[str, Any] = {}
        if audio_format:
            audio_params["format"] = audio_format
        payload = {
            "reqParams": {"text": text, "speaker": speaker},
            "audioParams": audio_params,
        }
        body = self.transport.request_json("POST", "/tts", json=payload)
        return TtsSingleResult(
            inference_id=body.get("inferenceId", ""),
            duration_ms=body.get("durationMs"),
            url=body.get("url", ""),
        )

    def estimate(self, text: str) -> dict[str, Any]:
        body = self.transport.request_json("POST", "/tts/estimate", json={"reqParams": {"text": text}})
        return body

    def list_voices(self) -> list[dict[str, Any]]:
        """音色清单（{"voices":[{code,displayName,gender,styleTag}]} 的 voices 数组）。"""
        body = self.transport.request_json("GET", "/tts/voices")
        voices = body.get("voices")
        return voices if isinstance(voices, list) else []

    def submit_task(self, text: str, speaker: str, audio_format: str | None = None) -> str:
        audio_params: dict[str, Any] = {}
        if audio_format:
            audio_params["format"] = audio_format
        payload = {
            "reqParams": {"text": text, "speaker": speaker},
            "audioParams": audio_params,
        }
        body = self.transport.request_json("POST", "/tts/tasks", json=payload)
        return body["taskId"]

    def get_task(self, task_no: str) -> TaskInfo:
        body = self.transport.request_json("GET", f"/tts/tasks/{task_no}")
        return TaskInfo(
            task_no=task_no,
            status=body.get("status", ""),
            total_units=body.get("totalUnits"),
            done_units=body.get("doneUnits"),
            result_url=body.get("resultUrl"),
            expire_at=body.get("expireAt"),
            error_msg=body.get("errorMsg"),
            raw=body,
        )
