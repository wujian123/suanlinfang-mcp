"""异常体系：本地配置问题（AuthError）与服务端错误（ApiError）分离。"""


class SuanlinfangError(Exception):
    """SDK 异常基类。"""


class SuanlinfangAuthError(SuanlinfangError):
    """本地侧鉴权配置缺失（无 API Key），非服务端拒绝。"""


class SuanlinfangApiError(SuanlinfangError):
    """服务端返回的非 2xx 错误（信封 {"error":{code,type,message},"requestId"}）。"""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str | None = None,
        code: str | None = None,
        request_id: str | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.code = code
        self.request_id = request_id
        self.retryable = retryable

    def __str__(self) -> str:
        parts = [f"[HTTP {self.status_code}] {self.message}"]
        if self.code:
            parts.append(f"code={self.code}")
        if self.error_type:
            parts.append(f"type={self.error_type}")
        if self.request_id:
            parts.append(f"requestId={self.request_id}")
        return " ".join(parts)
