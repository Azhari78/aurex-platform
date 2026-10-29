"""Web3 & MetaMask Wallet Adapter for Aurex Master Platform.

Manages EVM-compatible Web3 wallet state:
- Tracks connected address, network/chain ID, and native balances (ETH/MATIC)
- Integrates with Multi-chain DeFi Engine (Arbitrum, Polygon, Ethereum, Base)
- Provides telemetry to AIA AI Brain & Chat Assistant
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("aurex.adapters.web3")

CONFIG_FILE = Path("config/web3_wallet.json")

SUPPORTED_CHAINS = {
    "0x1": "Ethereum Mainnet",
    "0xa4b1": "Arbitrum One",
    "0x89": "Polygon POS",
    "0x2105": "Base",
    "0xaa36a7": "Sepolia Testnet",
    "1": "Ethereum Mainnet",
    "42161": "Arbitrum One",
    "137": "Polygon POS",
    "8453": "Base",
    "11155111": "Sepolia Testnet",
}


class Web3WalletAdapter:
    """Enterprise Web3 & MetaMask Wallet Adapter."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self._wallet_data: Dict[str, Any] = self._load_wallet()

    def _load_wallet(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to read web3 wallet config: {e}")
        return {
            "connected": False,
            "address": "",
            "chain_id": "0xa4b1",
            "chain_name": "Arbitrum One",
            "balance_eth": 0.0,
            "balance_usdc": 0.0,
            "protocols_active": ["Aave v3 (Arbitrum)"],
        }

    def connect_wallet(
        self,
        address: str,
        chain_id: str = "0xa4b1",
        balance_eth: float = 0.0,
        balance_usdc: float = 0.0
    ) -> Dict[str, Any]:
        """Record and persist an active MetaMask connection."""
        chain_name = SUPPORTED_CHAINS.get(str(chain_id), f"Chain {chain_id}")
        self._wallet_data = {
            "connected": True,
            "address": address.strip(),
            "chain_id": str(chain_id),
            "chain_name": chain_name,
            "balance_eth": float(balance_eth),
            "balance_usdc": float(balance_usdc),
            "protocols_active": ["Aave v3 (Arbitrum)"],
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self._wallet_data, indent=2), encoding="utf-8")
        return self.get_summary()

    def disconnect_wallet(self) -> None:
        """Disconnect wallet and reset state."""
        self._wallet_data["connected"] = False
        self._wallet_data["address"] = ""
        self._wallet_data["balance_eth"] = 0.0
        self._wallet_data["balance_usdc"] = 0.0
        if self.config_path.exists():
            try:
                self.config_path.write_text(json.dumps(self._wallet_data, indent=2), encoding="utf-8")
            except Exception:
                pass

    def get_summary(self) -> Dict[str, Any]:
        """Return combined status dictionary for dashboard & AIA telemetry."""
        addr = self._wallet_data.get("address", "")
        short_addr = f"{addr[:6]}...{addr[-4:]}" if len(addr) >= 10 else addr
        return {
            "connected": self._wallet_data.get("connected", False),
            "address": addr,
            "short_address": short_addr,
            "chain_id": self._wallet_data.get("chain_id", "0xa4b1"),
            "chain_name": self._wallet_data.get("chain_name", "Arbitrum One"),
            "balance_eth": self._wallet_data.get("balance_eth", 0.0),
            "balance_usdc": self._wallet_data.get("balance_usdc", 0.0),
            "protocols_active": self._wallet_data.get("protocols_active", ["Aave v3 (Arbitrum)"]),
        }


# Global adapter instance
WEB3_ADAPTER = Web3WalletAdapter()
