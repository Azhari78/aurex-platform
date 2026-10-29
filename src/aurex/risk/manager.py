"""Risk and Capital Authority.

Enforces portfolio-wide risk limits, position sizing, and capital preservation:
- Single-asset exposure concentration cap
- Market class concentration caps (FX, Crypto, DeFi)
- Daily portfolio drawdown circuit breaker
- Absolute veto authority over trade proposals
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Tuple
from aurex.core.models import AIAActionRequest, MarketType


class RiskVerdict:
    def __init__(self, approved: bool, reason: str, adjusted_principal: Decimal = Decimal("0")):
        self.approved = approved
        self.reason = reason
        self.adjusted_principal = adjusted_principal

    def __repr__(self) -> str:
        return f"<RiskVerdict approved={self.approved} reason='{self.reason}'>"


class RiskManager:
    """Independent Risk Gatekeeper."""

    def __init__(self, portfolio_capital: Decimal = Decimal("10000.00")):
        self.portfolio_capital = portfolio_capital
        # Market allocation caps (percentage of total capital)
        self.market_caps = {
            MarketType.FX: Decimal("0.45"),      # Max 45% in FX
            MarketType.CRYPTO: Decimal("0.35"),  # Max 35% in Crypto
            MarketType.DEFI: Decimal("0.40"),    # Max 40% in DeFi
        }
        self.single_asset_cap = Decimal("0.15")  # Max 15% in any single pair/token
        self.max_daily_drawdown_pct = 4.0        # Max 4% daily portfolio loss limit
        self.current_daily_loss_pct = 0.0

        # Current active open allocations
        self._active_allocations: Dict[str, Decimal] = {}

    def get_market_exposure(self, market: MarketType) -> Decimal:
        total = Decimal("0")
        for key, amt in self._active_allocations.items():
            if key.startswith(f"{market.value}:"):
                total += amt
        return total

    def evaluate_proposal(self, request: AIAActionRequest) -> RiskVerdict:
        """Evaluate if the proposal adheres to strict risk invariants."""
        # 1. Daily drawdown check
        if self.current_daily_loss_pct >= self.max_daily_drawdown_pct:
            return RiskVerdict(
                approved=False,
                reason=f"Daily drawdown limit ({self.max_daily_drawdown_pct}%) breached. Current loss: {self.current_daily_loss_pct}%."
            )

        requested_amount = request.budget.principal
        asset_key = f"{request.target_market.value}:{request.symbol}"
        current_asset_exposure = self._active_allocations.get(asset_key, Decimal("0"))
        new_asset_exposure = current_asset_exposure + requested_amount

        # 2. Single asset concentration check
        max_asset_amount = self.portfolio_capital * self.single_asset_cap
        if new_asset_exposure > max_asset_amount:
            return RiskVerdict(
                approved=False,
                reason=f"Single asset concentration breach for {request.symbol}. Max allowed: ${max_asset_amount}, Requested total: ${new_asset_exposure}."
            )

        # 3. Market class concentration check
        market_cap_ratio = self.market_caps.get(request.target_market, Decimal("0.30"))
        max_market_amount = self.portfolio_capital * market_cap_ratio
        current_market_exposure = self.get_market_exposure(request.target_market)
        new_market_exposure = current_market_exposure + requested_amount

        if new_market_exposure > max_market_amount:
            return RiskVerdict(
                approved=False,
                reason=f"Market class exposure cap breach for {request.target_market.value}. Max allowed: ${max_market_amount}, Requested total: ${new_market_exposure}."
            )

        return RiskVerdict(
            approved=True,
            reason="Risk and capital exposure requirements satisfied.",
            adjusted_principal=requested_amount
        )

    def register_position(self, market: MarketType, symbol: str, amount: Decimal) -> None:
        key = f"{market.value}:{symbol}"
        self._active_allocations[key] = self._active_allocations.get(key, Decimal("0")) + amount

    def close_position(self, market: MarketType, symbol: str, amount: Decimal) -> None:
        key = f"{market.value}:{symbol}"
        current = self._active_allocations.get(key, Decimal("0"))
        self._active_allocations[key] = max(Decimal("0"), current - amount)
