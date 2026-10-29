@echo off
title Aurex MT5 Bridge Sync to Cloud VPS
cd /d "%~dp0"
set PYTHONPATH=src

echo ================================================================================
echo           AUREX METATRADER 5 (MT5) - LIVE BRIDGE KE CLOUD VPS
echo ================================================================================
echo Menyegerakkan akaun MT5 Fauzan Azhari (5057835635) ke http://35.245.121.188:8000
echo.

python -m aurex.adapters.mt5_sync --target http://35.245.121.188:8000 --interval 2.0

pause
