"""Unit tests for Economics Authority and Risk Manager."""

from decimal import Decimal
import unittest
from aurex.core.models import (
    AIAActionRequest,
    ActionDirection,
    Budget,
    MarketType,
    Opportunity,
)
from aurex.economics.evaluator import EconomicsAuthority
from aurex.risk.manager import RiskManager


class TestEconomicsAndRisk(unittest.TestCase):
    def setUp(self):
        self.economics = EconomicsAuthority()
        self.risk = RiskManager(portfolio_capital=Decimal("10000.00"))

    def test_economics_viable_positive_ev(self):
        opp = Opportunity(
            opportunity_id="opp_1",
            engine_id="ENGINE_CRYPTO",
            market=MarketType.CRYPTO,
            symbol="BTC/USD",
            direction=ActionDirection.BUY,
            confidence_score=0.80,
            expected_return_pct=5.0,
            timeframe="H1",
            entry_price=Decimal("60000.00"),
            target_price=Decimal("63000.00"),  # +5%
            stop_loss=Decimal("58800.00"),     # -2%
            suggested_budget=Budget(
                total=Decimal("200.20"),
                principal=Decimal("200.00"),
                fees_allowance=Decimal("0.20"),
                currency="USD"
            )
        )
        verdict = self.economics.evaluate(opp)
        self.assertTrue(verdict.viable)
        self.assertGreater(verdict.net_ev_pct, 0.5)

    def test_economics_rejects_negative_ev(self):
        opp = Opportunity(
            opportunity_id="opp_2",
            engine_id="ENGINE_CRYPTO",
            market=MarketType.CRYPTO,
            symbol="BTC/USD",
            direction=ActionDirection.BUY,
            confidence_score=0.30,  # Low confidence
            expected_return_pct=1.0,
            timeframe="H1",
            entry_price=Decimal("60000.00"),
            target_price=Decimal("60500.00"),  # +0.83%
            stop_loss=Decimal("58000.00"),     # -3.33%
            suggested_budget=Budget(
                total=Decimal("205.00"),
                principal=Decimal("200.00"),
                fees_allowance=Decimal("5.00"),
                currency="USD"
            )
        )
        verdict = self.economics.evaluate(opp)
        self.assertFalse(verdict.viable)

    def test_risk_manager_single_asset_limit(self):
        # 15% of 10,000 is 1,500. A request for 2,000 must be rejected.
        req = AIAActionRequest(
            request_id="req_large",
            client_intent="LARGE_BET",
            target_market=MarketType.CRYPTO,
            symbol="BTC/USD",
            direction=ActionDirection.BUY,
            opportunity_ref="opp_large",
            budget=Budget(total=Decimal("2000.00"), principal=Decimal("2000.00")),
            max_loss=Decimal("100.00"),
            rationale="Too big",
            expiry_utc="2026-10-18T20:00:00Z"
        )
        verdict = self.risk.evaluate_proposal(req)
        self.assertFalse(verdict.approved)
        self.assertIn("concentration breach", verdict.reason)


if __name__ == "__main__":
    unittest.main()
