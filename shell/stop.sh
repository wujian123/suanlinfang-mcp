#!/bin/bash
# 停止 suanlinfang-mcp HTTP 常驻进程
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${PROJECT_DIR}/../logs/suanlinfang-mcp.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" || true
        echo "已停止 PID=$PID"
    else
        echo "PID=$PID 已不在运行"
    fi
    rm -f "$PID_FILE"
else
    echo "无 PID 文件，未在运行"
fi
