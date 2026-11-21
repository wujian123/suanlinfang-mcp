import logging
import time
from typing import Any, BinaryIO

import httpx

from suanlinfang.config import SdkConfig
from suanlinfang.errors import SuanlinfangApiError

logger = logging.getLogger("suanlinfang.sdk")

MAX_RETRIES = 3
RETRY_STATUS = (502, 503, 504)


def _default_sleep(seconds: float) -> None:
    time.sleep(seconds)


# 测试里 monkeypatch 此符号以免真实等待
_sleep = _default_sleep


class HttpTransport:
    """httpx 单点收口：鉴权 header、错误信封解析、5xx 退避重试。

    绝对 URL（OSS 上传 / 结果下载）不走鉴权，按调用方给的 headers 原样发。
    """

    def __init__(self, config: SdkConfig, client: httpx.Client | None = None):
        self.config = config
        self._client = client or httpx.Client(timeout=config.timeout)

    def close(self) -> None:
        self._client.close()

    def _headers(self) -> dict[str, str]:
        # Content-Type 不在此设置：json=/data= 由 httpx 按请求体类型自动带（表单写死 json 会被服务端 400）
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        if self.config.client_tag:
            headers["X-SLF-Client"] = self.config.client_tag
        return headers

    def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        json: Any | None = None,
        data: dict[str, Any] | None = None,
        content: bytes | BinaryIO | None = None,
        headers: dict[str, str] | None = None,
        authed: bool = True,
    ) -> httpx.Response:
        url = path_or_url if path_or_url.startswith("http") else f"{self.config.base_url}{path_or_url}"
        request_headers = dict(headers or {})
        if authed:
            request_headers.update(self._headers())
        retries = 0
        while True:
            try:
                response = self._client.request(
                    method, url, json=json, data=data, content=content, headers=request_headers
                )
            except httpx.TimeoutException as exc:
                # 超时不自动重试（计费可能已完成，见 API 文档），转成可重试语义错误由上层决策
                raise SuanlinfangApiError(
                    504,
                    "请求超时（推理冷启动或负载高时可能发生）。可直接重试；若担心重复计费，先查历史记录核对",
                    error_type="gateway_timeout",
                    retryable=True,
                ) from exc
            if response.status_code in RETRY_STATUS and retries < MAX_RETRIES:
                retries += 1
                delay = self._retry_after_seconds(response) or 0.5 * (2 ** (retries - 1))
                logger.warning("HTTP %s 命中可重试状态，第 %d 次重试（%.1fs 后）: %s", response.status_code, retries, delay, url)
                _sleep(delay)
                continue
            return response

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        json: Any | None = None,
        data: dict[str, Any] | None = None,
        authed: bool = True,
    ) -> dict[str, Any]:
        response = self._request(method, path_or_url, json=json, data=data, authed=authed)
        self._raise_for_error(response)
        body = response.json()
        return body if isinstance(body, dict) else {"_list": body}

    def put_bytes(self, url: str, content: bytes | BinaryIO, headers: dict[str, str]) -> None:
        """OSS 直传：成功 200 无响应体，非 2xx 直接抛。content 为字节或打开的文件对象。"""
        response = self._request("PUT", url, content=content, headers=headers, authed=False)
        self._raise_for_error(response)

    def get_json_absolute(self, url: str) -> dict[str, Any]:
        """现签结果 URL（result.json 等）的下载解析：无鉴权。"""
        response = self._request("GET", url, authed=False)
        self._raise_for_error(response)
        body = response.json()
        return body if isinstance(body, dict) else {"_list": body}

    def stream_to_file(self, url: str, file_path: str, max_bytes: int) -> int:
        """流式下载到本地文件（长音频 URL→任务链路用），返回实际字节数；超上限抛错。"""
        written = 0
        with self._client.stream("GET", url) as response:
            self._raise_for_error(response)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise SuanlinfangApiError(
                    413,
                    f"远端文件 {int(content_length)} 字节，超过上限 {max_bytes} 字节",
                    error_type="request_too_large",
                    retryable=False,
                )
            with open(file_path, "wb") as output:
                for chunk in response.iter_bytes():
                    written += len(chunk)
                    if written > max_bytes:
                        raise SuanlinfangApiError(
                            413,
                            f"下载超过上限 {max_bytes} 字节，中止",
                            error_type="request_too_large",
                            retryable=False,
                        )
                    output.write(chunk)
        return written

    def _raise_for_error(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        message = response.text[:500]
        error_type = None
        code = None
        request_id = response.headers.get("X-Request-Id")
        try:
            body = response.json()
            error = body.get("error") or {}
            message = error.get("message") or message
            error_type = error.get("type")
            code = error.get("code")
            request_id = body.get("requestId") or request_id
        except ValueError:
            pass
        raise SuanlinfangApiError(
            response.status_code,
            message,
            error_type=error_type,
            code=code,
            request_id=request_id,
            retryable=response.status_code >= 500,
        )
