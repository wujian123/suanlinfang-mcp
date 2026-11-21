import os

from suanlinfang.errors import SuanlinfangAuthError

# 生产入口必须用裸域：www 域名 443 全路径 301 到裸域，POST 跨 301 会方法漂移
DEFAULT_BASE_URL = "https://suanlinfang.cn/v1"

API_KEY_ENV = "SUANLINFANG_API_KEY"
BASE_URL_ENV = "SUANLINFANG_BASE_URL"


class SdkConfig:
    """客户端配置；base_url 不传时走 env 覆盖（dev 联调用），再退默认生产地址。

    client_tag 可选：渠道自报标识，随鉴权请求以 X-SLF-Client 头发出（服务端 channel 归因），
    由 MCP 壳从握手 clientInfo 推导（如 mcp-cursor）；裸 SDK 调用方不传即不报。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 120.0,
        client_tag: str | None = None,
    ):
        if not api_key or not api_key.strip():
            raise SuanlinfangAuthError(
                "缺少 API Key：请到控制台「API Key 管理」创建（nk- 前缀），"
                "https://suanlinfang.cn/consume-web/api-keys.html"
            )
        self.api_key = api_key.strip()
        resolved = base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout
        self.client_tag = (client_tag or "").strip() or None
