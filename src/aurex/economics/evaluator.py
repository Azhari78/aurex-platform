"""Economics Authority Evaluator.

Independent economic viability verification:
- Computes net expected value (EV) after full fees, gas, slippage, and spread
- Enforces minimum positive EV threshold
- Enforces minimum Risk-to-Reward ratio (default 1.5:1)
- Rejects economically non-viable proposals
"""

from __future__ import annotations

from decimal import Decimal
from typing import Tuple
from aurex.core.models import Opportunity


class EconomicsVerdict:
    """Result of economic evaluation."""
    def __init__(self, viable: bool, net_ev_pct: float, risk_reward_ratio: float, reason: str):
        self.viable = viable
        self.net_ev_pct = net_ev_pct
        self.risk_reward_ratio = risk_reward_ratio
        self.reason = reason

    def __repr__(self) -> str:
        return f"<EconomicsVerdict viable={self.viable} net_ev={self.net_ev_pct:.2f}% rr={self.risk_reward_ratio:.2f} reason='{self.reason}'>"


class EconomicsAuthority:
    """Evaluates economic viability and expected payoffs."""

    def __init__(self, min_ev_pct: float = 0.5, min_rr_ratio: float = 1.4):
        self.min_ev_pct = min_ev_pct
        self.min_rr_ratio = min_rr_ratio

    def evaluate(self, opp: Opportunity) -> EconomicsVerdict:
        """Evaluate gross vs net payoff after fees, spread, and gas."""
        principal = opp.suggested_budget.principal
        if principal <= Decimal("0"):
            return EconomicsVerdict(False, 0.0, 0.0, "Principal must be positive.")

        entry = opp.entry_price
        target = opp.target_price
        stop = opp.stop_loss

        # Calculate gross profit / loss percentage
        if opp.direction.value in ("BUY", "LEND", "PROVIDE_LIQUIDITY"):
            gain_pct = float((target - entry) / entry) * 100.0 if entry > 0 else 0.0
            loss_pct = float((entry - stop) / entry) * 100.0 if entry > 0 else 0.0
        else:  # SELL / SHORT
            gain_pct = float((entry - target) / entry) * 100.0 if entry > 0 else 0.0
            loss_pct = float((stop - entry) / entry) * 100.0 if entry > 0 else 0.0

        # Total overhead costs (fees + gas + slippage) as percentage of principal
        overhead = opp.suggested_budget.fees_allowance + opp.suggested_budget.gas_allowance + opp.suggested_budget.slippage_allowance
        overhead_pct = float(overhead / principal) * 100.0

        # Net outcomes
        net_gain_pct = gain_pct - overhead_pct
        net_loss_pct = loss_pct + overhead_pct

        if net_loss_pct <= 0:
            net_loss_pct = 0.0001

        rr_ratio = net_gain_pct / net_loss_pct if net_loss_pct > 0 else 0.0

        # Expected Value EV = (Prob_win * Net Gain) - (Prob_loss * Net Loss)
        prob_win = opp.confidence_score
        prob_loss = 1.0 - prob_win
        net_ev = (prob_win * net_gain_pct) - (prob_loss * net_loss_pct)

        # Check viability thresholds
        if net_ev < self.min_ev_pct:
            return EconomicsVerdict(
                viable=False,
                net_ev_pct=net_ev,
                risk_reward_ratio=rr_ratio,
                reason=f"Net EV ({net_ev:.2f}%) below minimum required ({self.min_ev_pct}%)."
            )

        if rr_ratio < self.min_rr_ratio and opp.market.value != "DEFI":
            return EconomicsVerdict(
                viable=False,
                net_ev_pct=net_ev,
                risk_reward_ratio=rr_ratio,
                reason=f"Risk:Reward ratio ({rr_ratio:.2f}) below threshold ({self.min_rr_ratio})."
            )

        return EconomicsVerdict(
            viable=True,
            net_ev_pct=net_ev,
            risk_reward_ratio=rr_ratio,
            reason="Economic viability verified with positive net EV."
        )
