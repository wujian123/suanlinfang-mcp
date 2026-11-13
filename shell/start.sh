#!/bin/bash
# suanlinfang-mcp HTTP 形态启动（照 pdf-translate-service/shell/start.sh 惯例）
# 用法：./shell/start.sh   ——「start 即重启」语义：先杀 PID 文件里的旧进程再启
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
LOG_FILE="${PROJECT_DIR}/../logs/suanlinfang-mcp.log"
PID_FILE="${PROJECT_DIR}/../logs/suanlinfang-mcp.pid"
PORT="${SUANLINFANG_MCP_PORT:-8090}"

mkdir -p "$(dirname "$LOG_FILE")"

# 停旧进程
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "停止旧进程 PID=$OLD_PID"
        kill "$OLD_PID" || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# 解释器：优先 python3.12（ECS1 = /usr/local/bin/python3.12，Miniconda 安装；本地回落系统 python3）
PYTHON_BIN="$(command -v python3.12 || command -v python3)"

# 首次运行：自建 venv 并安装 workspace 两包
if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "初始化 venv（首次）..."
    "${PYTHON_BIN}" -m venv "$VENV_DIR"
    "${VENV_DIR}/bin/pip" install -q -i https://pypi.tuna.tsinghua.edu.cn/simple \
        -e "${PROJECT_DIR}/packages/suanlinfang-sdk" \
        -e "${PROJECT_DIR}/packages/suanlinfang-mcp"
fi

# 启动（HTTP 形态，Streamable HTTP 端点 /mcp）
nohup "${VENV_DIR}/bin/python" -m suanlinfang_mcp.entry_http >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "已启动 PID=$NEW_PID，端口 ${PORT}（/mcp）"

# 健康检查：/healthz 最多等 30 秒
for i in $(seq 1 30); do
    if curl -s -f -o /dev/null "http://127.0.0.1:${PORT}/healthz"; then
        echo "健康检查通过（${i}s）"
        exit 0
    fi
    sleep 1
done

echo "健康检查超时（30s），查看日志：$LOG_FILE"
exit 1
