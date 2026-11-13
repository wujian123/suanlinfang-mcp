import os
import tempfile
from typing import Any
from urllib.parse import urlparse

from suanlinfang.http import HttpTransport
from suanlinfang.types import OcrResult, TaskInfo, UploadTicket

OCR_PDF_MAX_BYTES = 200 * 1024 * 1024


class OcrClient:
    def __init__(self, transport: HttpTransport):
        self.transport = transport

    def recognize_url(self, url: str, tier: str, prompt: str | None = None) -> OcrResult:
        """单图识别（公网 URL 引用，png/jpg/webp/bmp，≤20MB），同步返回。"""
        form: dict[str, Any] = {"url": url, "tier": tier}
        if prompt:
            form["prompt"] = prompt
        body = self.transport.request_json("POST", "/ocr/url", data=form)
        return self._parse_single(body)

    def recognize_base64(self, image_b64: str, tier: str, prompt: str | None = None) -> OcrResult:
        """单图识别（base64 直传）。"""
        form: dict[str, Any] = {"image": image_b64, "tier": tier}
        if prompt:
            form["prompt"] = prompt
        body = self.transport.request_json("POST", "/ocr/base64", data=form)
        return self._parse_single(body)

    @staticmethod
    def _parse_single(body: dict[str, Any]) -> OcrResult:
        words_result = body.get("wordsResult") or []
        return OcrResult(
            log_id=body.get("logId", ""),
            words=[item.get("words", "") for item in words_result],
            words_result_num=body.get("wordsResultNum", len(words_result)),
        )

    def request_pdf_ticket(self, file_name: str, size_bytes: int) -> UploadTicket:
        body = self.transport.request_json(
            "POST", "/ocr/upload-tickets", json={"fileName": file_name, "sizeBytes": size_bytes}
        )
        return UploadTicket(
            file_key=body["fileKey"],
            upload_url=body["uploadUrl"],
            method=body.get("method", "PUT"),
            headers=body.get("headers") or {},
            expire_at=body.get("expireAt"),
            max_size_bytes=body.get("maxSizeBytes"),
        )

    def upload_pdf(self, ticket: UploadTicket, content: bytes) -> None:
        """OSS 直传；content 可为字节或已打开的二进制文件对象（大文件流式）。"""
        self.transport.put_bytes(ticket.upload_url, content, ticket.headers)

    def submit_pdf_task(
        self,
        file_key: str,
        tier: str,
        prompt: str | None = None,
        file_name: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {"tier": tier, "fileKey": file_key}
        if prompt:
            payload["prompt"] = prompt
        if file_name:
            payload["fileName"] = file_name
        body = self.transport.request_json("POST", "/ocr/tasks", json=payload)
        return body["taskId"]

    def submit_pdf_from_url(
        self,
        url: str,
        tier: str,
        prompt: str | None = None,
        file_name: str | None = None,
    ) -> str:
        """PDF URL → 任务：流式下载（≤200MB）→ 签名 → OSS 直传 → 提交，返回 taskNo。"""
        derived_name = file_name or os.path.basename(urlparse(url).path) or "document.pdf"
        extension = os.path.splitext(derived_name)[1].lower()
        if extension != ".pdf":
            raise ValueError(
                f"异步识别仅支持 PDF（收到 {extension or '(无扩展名)'}）；单张图片请直接调 recognize_url"
            )
        with tempfile.TemporaryDirectory(prefix="suanlinfang-ocr-") as tmp_dir:
            local_path = os.path.join(tmp_dir, derived_name)
            size_bytes = self.transport.stream_to_file(url, local_path, OCR_PDF_MAX_BYTES)
            with open(local_path, "rb") as pdf_file:
                ticket = self.request_pdf_ticket(derived_name, size_bytes)
                # 流式上传（文件对象直传，200MB 级不整读进内存）
                self.upload_pdf(ticket, pdf_file)
        return self.submit_pdf_task(ticket.file_key, tier=tier, prompt=prompt, file_name=derived_name)

    def get_task(self, task_no: str) -> TaskInfo:
        body = self.transport.request_json("GET", f"/ocr/tasks/{task_no}")
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
