from dataclasses import dataclass, field
from typing import Any


@dataclass
class UploadTicket:
    """OSS 直传签名（upload-tickets 响应）。PUT 上传时 headers 必须逐字段照抄（Content-Type 参与签名）。"""

    file_key: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expire_at: str | None = None
    max_size_bytes: int | None = None


@dataclass
class TaskInfo:
    """异步任务查询结果（STT/TTS/OCR 共用任务模型）。"""

    task_no: str
    status: str
    total_units: int | None = None
    done_units: int | None = None
    result_url: str | None = None
    expire_at: str | None = None
    error_msg: str | None = None
    # success 且任务有全文产物（STT result.json）时填充
    text: str | None = None
    # 原始响应（透传未建模字段，供上层按需取）
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SttSingleResult:
    inference_id: str
    text: str
    duration_ms: int | None = None


@dataclass
class TtsSingleResult:
    inference_id: str
    duration_ms: int | None = None
    url: str = ""


@dataclass
class OcrResult:
    log_id: str
    words: list[str]
    words_result_num: int


@dataclass
class ImageTaskInfo:
    """生图任务查询结果（单张图单单元任务，doneUnits/totalUnits 恒 1/1）。"""

    task_no: str
    status: str
    total_units: int | None = None
    done_units: int | None = None
    result_url: str | None = None
    # 图生图任务的参考图现签回看链接（纯文生图无此字段）
    input_url: str | None = None
    seed: int | None = None
    expire_at: str | None = None
    error_msg: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenerateResult:
    """generate_image 高层封装结果。completed=False 表示等待超时未终态（降级，非错误）。"""

    completed: bool
    task_no: str
    status: str
    model: str
    result_url: str | None = None
    input_url: str | None = None
    expire_at: str | None = None
    seed: int | None = None
    error_msg: str | None = None
