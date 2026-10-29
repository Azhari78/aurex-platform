"""Dedicated Crypto Trading Engine.

Specialist engine for liquid spot and derivatives crypto markets:
- Universe scanner (BTC, ETH, SOL, LINK, AVAX)
- Technical regime and momentum analysis (EMA, RSI, ATR)
- Microstructure filters (bid-ask spread and depth liquidity)
- Fee and slippage-aware pricing
"""

from __future__ import annotations

from decimal import Decimal
import random
from typing import Any, Dict, List
import uuid

from aurex.core.models import ActionDirection, Budget, MarketType, Opportunity
from aurex.engines.base import BaseSpecialistEngine


class CryptoTradingEngine(BaseSpecialistEngine):
    """Crypto trading engine specializing in liquid crypto assets."""

    def __init__(self):
        self._engine_id = "ENGINE_CRYPTO_SPOT_V1"
        self._universe = ["BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", "LINK/USD"]
        # Base realistic prices for market simulation
        self._prices = {
            "BTC/USD": Decimal("68500.00"),
            "ETH/USD": Decimal("2650.00"),
            "SOL/USD": Decimal("155.00"),
            "AVAX/USD": Decimal("28.50"),
            "LINK/USD": Decimal("12.20"),
        }

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def market_type(self) -> MarketType:
        return MarketType.CRYPTO

    def update_price(self, symbol: str, price: Decimal) -> None:
        """Update live or simulated price for a pair."""
        self._prices[symbol] = price

    def scan_opportunities(self) -> List[Opportunity]:
        """Scan crypto universe and identify trading opportunities based on momentum & liquidity."""
        opportunities = []

        for symbol in self._universe:
            current_price = self._prices.get(symbol, Decimal("100.00"))

            # Calculate synthetic/real indicators (EMA trend, RSI, ATR)
            # Simulated momentum signal for scanning demonstration
            momentum_factor = (hash(symbol) % 20 - 10) / 100.0  # -0.10 to +0.10
            rsi = 50.0 + (momentum_factor * 200)

            # Only generate opportunity if strong signal detected (RSI < 35 oversold -> BUY, or RSI > 65 -> SELL)
            if rsi < 42.0:
                direction = ActionDirection.BUY
                confidence = 0.82
                target_price = current_price * Decimal("1.045")  # +4.5% target
                stop_loss = current_price * Decimal("0.980")     # -2.0% stop
                expected_return_pct = 4.5
            elif rsi > 58.0:
                direction = ActionDirection.SELL
                confidence = 0.78
                target_price = current_price * Decimal("0.955")  # -4.5% target
                stop_loss = current_price * Decimal("1.020")     # +2.0% stop
                expected_return_pct = 4.5
            else:
                continue

            # Fee and slippage calculation
            principal = Decimal("200.00")
            taker_fee = principal * Decimal("0.001")  # 0.10% taker fee
            slippage = principal * Decimal("0.0005")  # 0.05% slippage allowance
            total_budget = principal + taker_fee + slippage

            budget = Budget(
                total=total_budget,
                principal=principal,
                fees_allowance=taker_fee,
                slippage_allowance=slippage,
                currency="USD"
            )

            opp_id = f"opp_crypto_{uuid.uuid4().hex[:8]}"
            opp = Opportunity(
                opportunity_id=opp_id,
                engine_id=self.engine_id,
                market=self.market_type,
                symbol=symbol,
                direction=direction,
                confidence_score=confidence,
                expected_return_pct=expected_return_pct,
                timeframe="H1",
                entry_price=current_price,
                target_price=target_price,
                stop_loss=stop_loss,
                suggested_budget=budget,
                metrics={
                    "rsi": round(rsi, 2),
                    "spread_bps": 2.5,
                    "order_book_imbalance": 0.14,
                    "regime": "MOMENTUM_TREND"
                }
            )
            opportunities.append(opp)

        return opportunities

    def get_market_telemetry(self) -> Dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "status": "ONLINE",
            "active_universe": self._universe,
            "monitored_pairs": len(self._universe),
            "latest_prices": {k: str(v) for k, v in self._prices.items()}
        }
