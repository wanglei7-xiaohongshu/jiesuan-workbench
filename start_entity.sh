#!/usr/bin/env bash
# 结算工作台 Entity 版 - 一键启动脚本
# 用法: bash start_entity.sh [端口，默认8766]

set -e

PORT="${1:-8766}"
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
if [ ! -f "${SCRIPT_DIR}/结算工作台-entity版.html" ]; then
  echo "❌ 当前目录缺少「结算工作台-entity版.html」，请检查文件后再运行"
  exit 1
fi

echo ""
echo "🚀 启动 结算工作台 Entity 版（端口 ${PORT}）..."
echo ""

cd "$SCRIPT_DIR"
PORT="$PORT" python3 server_entity.py
