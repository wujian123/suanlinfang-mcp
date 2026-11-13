import os

from suanlinfang_mcp.server import mcp

DEFAULT_PORT = 8090
PORT_ENV = "SUANLINFANG_MCP_PORT"

# PORT 是容器/函数计算（FC）等托管环境注入端口的事实标准：
# 命中时绑 0.0.0.0（托管平台从外部访问），否则默认本机回环（ECS1 姿势，经 nginx 反代）
FC_PORT_ENV = "PORT"


def main() -> None:
    """Streamable HTTP 入口：常驻服务形态（ECS1 部署，经 nginx /mcp 反代对外）。

    端点路径默认 /mcp（如 http://127.0.0.1:8090/mcp）；健康探针 GET /healthz。
    """
    fc_port = os.environ.get(FC_PORT_ENV)
    if os.environ.get(PORT_ENV):
        port = int(os.environ[PORT_ENV])
        host = "127.0.0.1"
    elif fc_port:
        port = int(fc_port)
        host = "0.0.0.0"
    else:
        port = DEFAULT_PORT
        host = "127.0.0.1"
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
