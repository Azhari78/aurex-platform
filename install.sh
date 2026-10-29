#!/usr/bin/env bash
set -e

echo "================================================================================"
echo "          AUREX MASTER PLATFORM v1.3.1 - LINUX SETUP SCRIPT                     "
echo "================================================================================"

echo "[1/4] Mengemas kini pakej sistem Ubuntu/Debian..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv curl

echo "[2/4] Membuat Python Virtual Environment (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

echo "[3/4] Mengaktifkan venv dan memasang dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[4/4] Memberikan kebenaran execute pada skrip..."
chmod +x start.sh

echo "================================================================================"
echo "Pemasangan berjaya! Untuk jalankan platform:"
echo "  source venv/bin/activate"
echo "  ./start.sh"
echo "================================================================================"
