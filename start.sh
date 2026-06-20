#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "已创建 .env，请填入 LLM_API_KEY 后重新运行"
  exit 1
fi

mkdir -p data/sessions

# error 48 = 端口被占用，先释放 8080
PORT="${APP_PORT:-8080}"
OLD_PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$OLD_PIDS" ]; then
  echo "端口 $PORT 已被占用，正在停止旧进程: $OLD_PIDS"
  kill $OLD_PIDS 2>/dev/null || true
  sleep 1
fi

echo "Starting Copilot at http://127.0.0.1:$PORT"
echo "Chat UI: http://127.0.0.1:$PORT/"
python run.py
