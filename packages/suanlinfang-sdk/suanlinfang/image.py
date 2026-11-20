import os
import tempfile
from typing import Any, Callable
from urllib.parse import urlparse

from suanlinfang import http
from suanlinfang.http import HttpTransport
from suanlinfang.types import ImageGenerateResult, ImageTaskInfo, UploadTicket

# generate_image 未显式指定 model 时的默认：文生图走性价比档，图生图走唯一真正消费参考图的编辑档
DEFAULT_TEXT_IMAGE_MODEL = "flux2-klein"
DEFAULT_EDIT_IMAGE_MODEL = "qwen-image-edit-2511"
IMAGE_INIT_MAX_BYTES = 10 * 1024 * 1024
IMAGE_INIT_EXTENSIONS = (".png", ".jpg", ".jpeg")
POLL_INTERVAL_SECONDS = 3.0

# 任务终态（与 api-common 异步任务状态机一致）
TERMINAL_STATUSES = ("success", "failed", "expired")


class ImageClient:
    def __init__(self, transport: HttpTransport):
        self.transport = transport

    def list_models(self) -> list[dict[str, Any]]:
        """在线模型与实时牌价（{"data":[{id, pricing}]} 的 data 数组）。"""
        body = self.transport.request_json("GET", "/image/models")
        data = body.get("data")
        return data if isinstance(data, list) else []

    def submit_task(
        self,
        model: str,
        prompt: str,
        init_image_key: str | None = None,
        seed: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {"model": model, "prompt": prompt}
        if init_image_key:
            payload["initImageKey"] = init_image_key
        if seed is not None:
            payload["seed"] = seed
        body = self.transport.request_json("POST", "/image/tasks", json=payload)
        return body["taskId"]

    def get_task(self, task_no: str) -> ImageTaskInfo:
        body = self.transport.request_json("GET", f"/image/tasks/{task_no}")
        return ImageTaskInfo(
            task_no=task_no,
            status=body.get("status", ""),
            total_units=body.get("totalUnits"),
            done_units=body.get("doneUnits"),
            result_url=body.get("resultUrl"),
            input_url=body.get("inputUrl"),
            seed=body.get("seed"),
            expire_at=body.get("expireAt"),
            error_msg=body.get("errorMsg"),
            raw=body,
        )

    def request_ticket(self, file_name: str, size_bytes: int) -> UploadTicket:
        body = self.transport.request_json(
            "POST", "/image/upload-tickets", json={"fileName": file_name, "sizeBytes": size_bytes}
        )
        return UploadTicket(
            file_key=body["fileKey"],
            upload_url=body["uploadUrl"],
            method=body.get("method", "PUT"),
            headers=body.get("headers") or {},
            expire_at=body.get("expireAt"),
            max_size_bytes=body.get("maxSizeBytes"),
        )

    def upload_init_image(self, url: str, file_name: str | None = None) -> str:
        """参考图公网 URL → OSS 直传，返回 fileKey（提交图生图任务用）。

        复刻 STT 长音频 URL→任务链路：流式下载（≤10MB）→ 签票 → 直传。
        """
        derived_name = file_name or os.path.basename(urlparse(url).path) or "reference.png"
        extension = os.path.splitext(derived_name)[1].lower()
        if extension not in IMAGE_INIT_EXTENSIONS:
            raise ValueError(
                f"参考图扩展名 {extension or '(无)'} 不受支持（{'/'.join(IMAGE_INIT_EXTENSIONS)}）；"
                "请通过 file_name 指定正确扩展名"
            )
        with tempfile.TemporaryDirectory(prefix="suanlinfang-image-") as tmp_dir:
            local_path = os.path.join(tmp_dir, derived_name)
            size_bytes = self.transport.stream_to_file(url, local_path, IMAGE_INIT_MAX_BYTES)
            with open(local_path, "rb") as image_file:
                ticket = self.request_ticket(derived_name, size_bytes)
                self.transport.put_bytes(ticket.upload_url, image_file, ticket.headers)
        return ticket.file_key

    def generate_image(
        self,
        prompt: str,
        model: str | None = None,
        init_image_url: str | None = None,
        seed: int | None = None,
        wait_seconds: float = 120.0,
        on_progress: Callable[[str, float, float], None] | None = None,
    ) -> ImageGenerateResult:
        """生图高层封装：解析默认模型 →（图生图）直传参考图 → 提交 → 原地轮询直到终态或超时。

        超时未终态不抛错，返回 completed=False（任务不丢失，可用 get_task 续查）；
        failed/expired 终态也以结果字段表达，由上层决定报错姿势。
        on_progress(status, elapsed_seconds, wait_seconds) 每轮询一次回调。
        """
        resolved_model = model
        if not resolved_model:
            resolved_model = DEFAULT_EDIT_IMAGE_MODEL if init_image_url else DEFAULT_TEXT_IMAGE_MODEL
        init_image_key = self.upload_init_image(init_image_url) if init_image_url else None
        task_no = self.submit_task(resolved_model, prompt, init_image_key=init_image_key, seed=seed)

        elapsed = 0.0
        while True:
            # 经模块属性调 _sleep（而非 from-import 绑定），测试 monkeypatch suanlinfang.http._sleep 才能生效
            http._sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
            info = self.get_task(task_no)
            if on_progress:
                on_progress(info.status, elapsed, wait_seconds)
            if info.status in TERMINAL_STATUSES:
                return self._to_generate_result(task_no, resolved_model, info, completed=True)
            if elapsed >= wait_seconds:
                return self._to_generate_result(task_no, resolved_model, info, completed=False)

    @staticmethod
    def _to_generate_result(
        task_no: str, model: str, info: ImageTaskInfo, completed: bool
    ) -> ImageGenerateResult:
        return ImageGenerateResult(
            completed=completed,
            task_no=task_no,
            status=info.status,
            model=model,
            result_url=info.result_url,
            input_url=info.input_url,
            expire_at=info.expire_at,
            seed=info.seed,
            error_msg=info.error_msg,
        )


__all__ = [
    "ImageClient",
    "DEFAULT_TEXT_IMAGE_MODEL",
    "DEFAULT_EDIT_IMAGE_MODEL",
    "TERMINAL_STATUSES",
]
