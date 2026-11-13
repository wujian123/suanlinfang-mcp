import os

try:
    from fastmcp.server.dependencies import get_http_headers
except ImportError:
    get_http_headers = None

from fastmcp.exceptions import ToolError

from suanlinfang import API_KEY_ENV

KEY_MANAGE_URL = "https://suanlinfang.cn/consume-web/api-keys.html"

NO_KEY_GUIDANCE = (
    "缺少算邻坊 API Key。请到控制台「API Key 管理」创建（nk- 前缀）：\n{url}\n"
    "配置方式：远程 HTTP 客户端在请求头带 X-SLF-Api-Key；"
    "本地/魔搭托管的 stdio 形态设置环境变量 {env}。"
).format(url=KEY_MANAGE_URL, env=API_KEY_ENV)


def _headers_lower() -> dict[str, str]:
    if get_http_headers is None:
        return {}
    try:
        headers = get_http_headers()
    except Exception:
        return {}
    return {str(k).lower(): str(v) for k, v in (headers or {}).items()}


def resolve_api_key() -> str:
    """鉴权解析（每请求调用，server 无状态）：
    HTTP 传输请求头 X-SLF-Api-Key → Authorization Bearer → 环境变量（stdio/魔搭姿势）→ 引导报错。
    """
    headers = _headers_lower()
    key = headers.get("x-slf-api-key", "").strip()
    if not key:
        authorization = headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            key = authorization[7:].strip()
    if not key:
        key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise ToolError(NO_KEY_GUIDANCE)
    return key
