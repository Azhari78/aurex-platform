@echo off
title AUREX Master Platform v1.3.1
cd /d "%~dp0"
set PYTHONPATH=src

echo ================================================================================
echo           AUREX MASTER PLATFORM v1.3.1 - INSTITUTIONAL TERMINAL
echo ================================================================================
echo Memulakan pelayan dashboard...
echo Sila tunggu, pelayar web akan dibuka secara automatik...
echo.

:: Tunggu 2 saat dan buka browser automatik ke localhost
start "" http://127.0.0.1:8000

:: Jalankan uvicorn server
python -m uvicorn aurex.dashboard.app:app --host 127.0.0.1 --port 8000

pause
