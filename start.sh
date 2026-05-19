#!/bin/bash
# 个人工作报告邮件助手启动脚本

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8765}"
LOG_FILE="$APP_DIR/app.log"

cd "$APP_DIR" || exit 1

echo "========================================"
echo "启动个人工作报告邮件助手"
echo "目录: $APP_DIR"
echo "监听: $HOST"
echo "端口: $PORT"
echo "日志: $LOG_FILE"
echo "========================================"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

# 后台启动
HOST="$HOST" PORT="$PORT" nohup python3 app.py > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$APP_DIR/app.pid"
echo "已启动，PID: $PID"
echo "访问地址: http://$HOST:$PORT"
echo "英文相对地址: /personal-office-assistant"
echo "完整访问地址: http://$HOST:$PORT/personal-office-assistant"
echo ""
echo "停止命令: kill \$(cat app.pid)"
