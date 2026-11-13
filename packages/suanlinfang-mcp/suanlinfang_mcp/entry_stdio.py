from suanlinfang_mcp.server import mcp


def main() -> None:
    """stdio 入口：本地/魔搭托管形态（用户经环境变量 SUANLINFANG_API_KEY 注入密钥）。"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
