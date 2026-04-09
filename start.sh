#!/usr/bin/env bash
# 结算工作台 - 一键启动脚本
# 用法: bash start.sh [端口，默认8765]

set -e

PORT="${1:-8765}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 检查 Python3
if ! command -v python3 &>/dev/null; then
  echo "❌ 未找到 python3，请先安装 Python 3.8+"
  exit 1
fi

# 检查/安装依赖
echo "📦 检查依赖..."
python3 -c "import flask, flask_cors" 2>/dev/null || {
  echo "📦 安装依赖 flask flask-cors ..."
  pip3 install flask flask-cors
}

# 检查 HTML 文件是否存在
if [ ! -f "结算工作台.html" ]; then
  echo "❌ 当前目录缺少「结算工作台.html」，请把 HTML 文件放到同一目录后再运行"
  exit 1
fi

# 复制 server.py（如果不存在）
if [ ! -f "server.py" ]; then
  cp "$SCRIPT_DIR/../assets/server.py" ./server.py
  echo "✅ 已复制 server.py 到当前目录"
fi

echo ""
PORT="$PORT" python3 server.py
