import os
import tempfile
from urllib.parse import urlparse

from suanlinfang.http import HttpTransport
from suanlinfang.types import SttSingleResult, TaskInfo, UploadTicket

STT_MAX_TASK_BYTES = 500 * 1024 * 1024
SUPPORTED_EXTENSIONS = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac")


class SttClient:
    def __init__(self, transport: HttpTransport):
        self.transport = transport

    def transcribe_url(self, url: str, language: str | None = None, context: str | None = None) -> SttSingleResult:
        """单笔转写（公网 URL，音频 ≤3 分钟 / ≤20MB），同步返回。"""
        form = {"url": url}
        if language:
            form["language"] = language
        if context:
            form["context"] = context
        body = self.transport.request_json("POST", "/stt/url", data=form)
        result = body.get("result") or {}
        audio_info = body.get("audioInfo") or {}
        return SttSingleResult(
            inference_id=body.get("inferenceId", ""),
            text=result.get("text", ""),
            duration_ms=audio_info.get("durationMs"),
        )

    def request_ticket(self, file_name: str, size_bytes: int) -> UploadTicket:
        body = self.transport.request_json(
            "POST", "/stt/upload-tickets", json={"fileName": file_name, "sizeBytes": size_bytes}
        )
        return UploadTicket(
            file_key=body["fileKey"],
            upload_url=body["uploadUrl"],
            method=body.get("method", "PUT"),
            headers=body.get("headers") or {},
            expire_at=body.get("expireAt"),
            max_size_bytes=body.get("maxSizeBytes"),
        )

    def upload_file(self, ticket: UploadTicket, content: bytes) -> None:
        """OSS 直传；content 可为字节或已打开的二进制文件对象（大文件流式）。"""
        self.transport.put_bytes(ticket.upload_url, content, ticket.headers)

    def submit_task(
        self,
        file_key: str,
        language: str | None = None,
        context: str | None = None,
        file_name: str | None = None,
    ) -> str:
        payload: dict = {"audio": {"url": file_key}}
        if language:
            payload["language"] = language
        if context:
            payload["context"] = context
        if file_name:
            payload["fileName"] = file_name
        body = self.transport.request_json("POST", "/stt/tasks", json=payload)
        return body["taskId"]

    def get_task(self, task_no: str) -> TaskInfo:
        body = self.transport.request_json("GET", f"/stt/tasks/{task_no}")
        info = TaskInfo(
            task_no=task_no,
            status=body.get("status", ""),
            total_units=body.get("totalUnits"),
            done_units=body.get("doneUnits"),
            result_url=body.get("resultUrl"),
            expire_at=body.get("expireAt"),
            error_msg=body.get("errorMsg"),
            raw=body,
        )
        if info.status == "success" and info.result_url:
            result_body = self.transport.get_json_absolute(info.result_url)
            info.text = result_body.get("text")
        return info

    def transcribe_url_to_task(
        self,
        url: str,
        language: str | None = None,
        context: str | None = None,
        file_name: str | None = None,
    ) -> str:
        """长音频 URL → 任务：流式下载（≤500MB）→ 签名 → OSS 直传 → 提交任务，返回 taskNo。"""
        derived_name = file_name or os.path.basename(urlparse(url).path) or "audio.mp3"
        extension = os.path.splitext(derived_name)[1].lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"音频扩展名 {extension or '(无)'} 不受支持（{ '/'.join(SUPPORTED_EXTENSIONS) }）；"
                "请通过 file_name 指定正确扩展名"
            )
        with tempfile.TemporaryDirectory(prefix="suanlinfang-stt-") as tmp_dir:
            local_path = os.path.join(tmp_dir, derived_name)
            size_bytes = self.transport.stream_to_file(url, local_path, STT_MAX_TASK_BYTES)
            with open(local_path, "rb") as audio_file:
                ticket = self.request_ticket(derived_name, size_bytes)
                # 流式上传（文件对象直传，500MB 级不整读进内存）
                self.upload_file(ticket, audio_file)
        return self.submit_task(ticket.file_key, language=language, context=context, file_name=derived_name)
