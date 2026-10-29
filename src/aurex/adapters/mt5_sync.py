"""Aurex MT5 Bridge Sync Client.

Streams real-time account info and positions from a local Windows MetaTrader 5 terminal
to the Aurex Cloud / VPS dashboard (e.g. http://35.245.121.188:8000).
"""

from __future__ import annotations

import argparse
import json
import time
import requests

from aurex.adapters.mt5_adapter import MT5_ADAPTER


def main():
    parser = argparse.ArgumentParser(description="Sync local MT5 to Aurex VPS")
    parser.add_argument("--target", default="http://127.0.0.1:8000", help="Target Aurex API URL")
    parser.add_argument("--interval", type=float, default=2.0, help="Sync interval in seconds")
    args = parser.parse_args()

    api_url = f"{args.target.rstrip('/')}/api/mt5/sync"
    print("=" * 70)
    print("       AUREX METATRADER 5 (MT5) CLOUD SYNC BRIDGE                     ")
    print("=" * 70)
    print(f"Target API Server : {api_url}")
    print(f"Sync Interval     : {args.interval}s")
    print("Initializing MetaTrader 5...")

    if not MT5_ADAPTER.connect():
        print(f"❌ Failed to connect to MT5: {MT5_ADAPTER._last_error}")
        return

    acc = MT5_ADAPTER.refresh_account_info()
    print(f"✅ Connected to MT5: {acc.get('name')} | Login: {acc.get('login')} | Server: {acc.get('server')}")
    print(f"💰 Balance: {acc.get('currency')} {acc.get('balance'):,.2f} | Equity: {acc.get('equity'):,.2f}")
    print("\nStarting live synchronization loop... (Press Ctrl+C to stop)")

    while True:
        try:
            info = MT5_ADAPTER.refresh_account_info()
            positions = MT5_ADAPTER.get_open_positions()

            payload = {
                **info,
                "open_positions": positions
            }

            resp = requests.post(api_url, json=payload, timeout=5)
            if resp.status_code == 200:
                print(f"[{time.strftime('%H:%M:%S')}] 🟢 SYNC OK: {info.get('currency')} {info.get('balance'):,.2f} | Open: {len(positions)} orders", end="\r")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Sync warning HTTP {resp.status_code}")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ Sync error: {e}")

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
