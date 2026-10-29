"""MetaTrader 5 (MT5) Real-Time Demo/Live Account Adapter for Aurex Master Platform.

Provides seamless integration with MetaTrader 5 terminals:
- Live Account Metrics (Balance, Equity, Margin, Free Margin, Profit, Currency, Leverage)
- Real-time Open Positions tracking
- Market Tick Stream (EUR/USD, GBP/USD, USD/JPY, XAU/USD, etc.)
- Autonomous & Manual Execution (BUY / SELL, SL, TP, Close Position)
- Graceful fallback for non-Windows / Linux server environments
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aurex.adapters.mt5")

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False


CONFIG_FILE = Path("config/mt5_credentials.json")
DEFAULT_CREDENTIALS = {
    "login": 5057835635,
    "password": "-7SuFcBc",
    "server": "MetaQuotes-Demo",
    "terminal_path": r"C:\Program Files\MetaTrader 5\terminal64.exe",
    "auto_connect": True,
}


class MT5Adapter:
    """Enterprise MT5 Broker Adapter for Aurex."""

    def __init__(self, credentials_path: Optional[Path] = None):
        self.config_path = credentials_path or CONFIG_FILE
        self._credentials = self._load_credentials()
        self._is_connected = False
        self._last_error = ""
        self._cached_account_info: Dict[str, Any] = {}
        self._cached_positions: List[Dict[str, Any]] = []

    def _load_credentials(self) -> Dict[str, Any]:
        """Load stored credentials or fallback to default configuration."""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                return {**DEFAULT_CREDENTIALS, **data}
            except Exception as e:
                logger.warning(f"Failed to read MT5 credentials: {e}")
        return dict(DEFAULT_CREDENTIALS)

    def save_credentials(
        self,
        login: int,
        password: str,
        server: str,
        terminal_path: Optional[str] = None
    ) -> None:
        """Persist MT5 credentials securely."""
        self._credentials["login"] = int(login)
        self._credentials["password"] = password
        self._credentials["server"] = server
        if terminal_path:
            self._credentials["terminal_path"] = terminal_path
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self._credentials, indent=2), encoding="utf-8")

    @property
    def is_available(self) -> bool:
        """True if the MetaTrader5 Python C-extension is present in this environment."""
        return MT5_AVAILABLE

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        terminal_path: Optional[str] = None
    ) -> bool:
        """Connect and authenticate to MetaTrader 5 terminal."""
        if not MT5_AVAILABLE:
            self._last_error = "MetaTrader5 library is only available on Windows environments."
            self._is_connected = False
            return False

        use_login = login or self._credentials.get("login")
        use_password = password or self._credentials.get("password")
        use_server = server or self._credentials.get("server")
        use_path = terminal_path or self._credentials.get("terminal_path")

        try:
            # Initialize terminal
            init_success = False
            if use_path and os.path.exists(use_path):
                init_success = mt5.initialize(use_path)
            else:
                init_success = mt5.initialize()

            if not init_success:
                err = mt5.last_error()
                self._last_error = f"MT5 initialization failed: {err}"
                self._is_connected = False
                return False

            # Authenticate with credentials
            login_success = mt5.login(
                login=int(use_login),
                password=str(use_password),
                server=str(use_server)
            )

            if not login_success:
                err = mt5.last_error()
                self._last_error = f"MT5 login failed for account {use_login} on {use_server}: {err}"
                self._is_connected = False
                return False

            self._is_connected = True
            self._last_error = ""
            self.save_credentials(use_login, use_password, use_server, use_path)
            self.refresh_account_info()
            return True

        except Exception as e:
            self._last_error = f"Exception connecting to MT5: {str(e)}"
            self._is_connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect and release terminal resources."""
        if MT5_AVAILABLE and self._is_connected:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self._is_connected = False

    def refresh_account_info(self) -> Dict[str, Any]:
        """Fetch real-time account telemetry from MT5."""
        if not MT5_AVAILABLE or not self._is_connected:
            return self.get_summary()

        try:
            acc = mt5.account_info()
            if acc:
                self._cached_account_info = {
                    "connected": True,
                    "name": acc.name,
                    "login": acc.login,
                    "server": acc.server,
                    "currency": acc.currency,
                    "leverage": acc.leverage,
                    "balance": float(acc.balance),
                    "equity": float(acc.equity),
                    "profit": float(acc.profit),
                    "margin": float(acc.margin),
                    "margin_free": float(acc.margin_free),
                    "margin_level": float(acc.margin_level) if acc.margin > 0 else 0.0,
                    "trade_mode": "DEMO" if acc.trade_mode == 0 else "CONTEST" if acc.trade_mode == 1 else "LIVE",
                }
            return self._cached_account_info
        except Exception as e:
            self._last_error = f"Error reading account info: {e}"
            return self.get_summary()

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Fetch all currently open positions from MT5."""
        if not MT5_AVAILABLE or not self._is_connected:
            return self._cached_positions

        try:
            positions = mt5.positions_get()
            pos_list = []
            if positions:
                for p in positions:
                    direction = "BUY" if p.type == 0 else "SELL"
                    pos_list.append({
                        "ticket": int(p.ticket),
                        "symbol": p.symbol,
                        "direction": direction,
                        "volume": float(p.volume),
                        "price_open": float(p.price_open),
                        "price_current": float(p.price_current),
                        "sl": float(p.sl),
                        "tp": float(p.tp),
                        "profit": round(float(p.profit), 2),
                        "swap": round(float(p.swap), 2),
                        "time": p.time,
                        "comment": p.comment,
                    })
            self._cached_positions = pos_list
            return pos_list
        except Exception as e:
            self._last_error = f"Error reading positions: {e}"
            return self._cached_positions

    def get_symbol_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieve live bid/ask quote tick for an instrument."""
        if not MT5_AVAILABLE or not self._is_connected:
            return None

        try:
            mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                return {
                    "symbol": symbol,
                    "bid": float(tick.bid),
                    "ask": float(tick.ask),
                    "spread": round(float(tick.ask - tick.bid), 5),
                    "time": tick.time,
                }
        except Exception:
            pass
        return None

    def place_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "Aurex AI"
    ) -> Dict[str, Any]:
        """Execute an institutional order directly on MT5 demo/live."""
        if not MT5_AVAILABLE or not self._is_connected:
            return {"success": False, "error": "MT5 is not connected"}

        try:
            mt5.symbol_select(symbol, True)
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return {"success": False, "error": f"Symbol {symbol} not found in MT5"}

            order_type = mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid

            # Determine appropriate filling mode
            filling = mt5.ORDER_FILLING_IOC
            if symbol_info.filling_mode & 1:
                filling = mt5.ORDER_FILLING_FOK
            elif symbol_info.filling_mode & 2:
                filling = mt5.ORDER_FILLING_IOC

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": order_type,
                "price": price,
                "sl": float(sl),
                "tp": float(tp),
                "deviation": 20,
                "magic": 888123,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                return {
                    "success": True,
                    "order_id": result.order,
                    "volume": result.volume,
                    "price": result.price,
                    "bid": result.bid,
                    "ask": result.ask,
                    "comment": result.comment,
                }
            else:
                ret_msg = result.comment if result else mt5.last_error()
                return {"success": False, "error": f"Order rejected by broker: {ret_msg}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_position(self, ticket: int) -> Dict[str, Any]:
        """Close an active position by ticket."""
        if not MT5_AVAILABLE or not self._is_connected:
            return {"success": False, "error": "MT5 is not connected"}

        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                return {"success": False, "error": f"Position ticket {ticket} not found"}

            pos = positions[0]
            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(pos.symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": price,
                "deviation": 20,
                "magic": 888123,
                "comment": "Aurex Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                return {"success": True, "ticket": ticket, "profit": pos.profit}
            else:
                ret_msg = result.comment if result else mt5.last_error()
                return {"success": False, "error": f"Close rejected: {ret_msg}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_from_sync(self, data: Dict[str, Any]) -> None:
        """Update cached MT5 state from an external sync bridge."""
        self._cached_account_info = {
            "connected": data.get("connected", True),
            "name": data.get("name", "Fauzan Azhari"),
            "login": data.get("login", 5057835635),
            "server": data.get("server", "MetaQuotes-Demo"),
            "currency": data.get("currency", "USD"),
            "leverage": data.get("leverage", 100),
            "balance": float(data.get("balance", 10000.0)),
            "equity": float(data.get("equity", 10000.0)),
            "profit": float(data.get("profit", 0.0)),
            "margin": float(data.get("margin", 0.0)),
            "margin_free": float(data.get("margin_free", 10000.0)),
            "margin_level": float(data.get("margin_level", 0.0)),
            "trade_mode": data.get("trade_mode", "DEMO"),
        }
        self._cached_positions = data.get("open_positions", [])
        self._is_connected = True

    def get_summary(self) -> Dict[str, Any]:
        """Return combined status dictionary for dashboard & telemetry."""
        if self._is_connected and self._cached_account_info:
            return {
                **self._cached_account_info,
                "open_positions_count": len(self._cached_positions),
                "open_positions": self._cached_positions,
                "last_error": self._last_error,
            }
        
        return {
            "connected": False,
            "login": self._credentials.get("login", 5057835635),
            "server": self._credentials.get("server", "MetaQuotes-Demo"),
            "name": "Fauzan Azhari",
            "balance": 10000.0,
            "equity": 10000.0,
            "profit": 0.0,
            "currency": "USD",
            "leverage": 100,
            "open_positions_count": 0,
            "open_positions": [],
            "last_error": self._last_error,
            "library_available": MT5_AVAILABLE,
        }


# Global adapter instance
MT5_ADAPTER = MT5Adapter()
