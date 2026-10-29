#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

export PYTHONPATH="src"
PORT="${PORT:-8000}"

echo "================================================================================"
echo "          AUREX MASTER PLATFORM v1.3.1 - LINUX VPS DEPLOYMENT                  "
echo "================================================================================"

echo "Memeriksa dan menghentikan proses lama di port ${PORT}..."
fuser -k ${PORT}/tcp 2>/dev/null || true
pkill -f "uvicorn aurex.dashboard.app" 2>/dev/null || true
sleep 1

echo "Memulakan pelayan terkini di 0.0.0.0:${PORT} ..."
echo "Buka pelayar di: http://<IP_VPS_ANDA>:${PORT}"
echo "================================================================================"

python3 -m uvicorn aurex.dashboard.app:app --host 0.0.0.0 --port "$PORT"
