"""Unit tests for Global Governor Authority and atomic authorization consumption."""

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from aurex.core.governor import (
    AuthorizationExpiredError,
    GlobalGovernor,
    GovernorError,
    KillSwitchActiveError,
    ReplayAuthorizationError,
)
from aurex.core.identity import IdentityManager
from aurex.core.ledger import GlobalLedger
from aurex.core.models import (
    AIAActionRequest,
    ActionDirection,
    Budget,
    MarketType,
    ProposalStatus,
)


class TestGlobalGovernor(unittest.TestCase):
    def setUp(self):
        self.ledger = GlobalLedger()
        self.ledger.deposit("acc1", "USD", Decimal("5000.00"))
        self.governor = GlobalGovernor(ledger=self.ledger)
        self.identity = IdentityManager()

        self.budget = Budget(
            total=Decimal("200.50"),
            principal=Decimal("200.00"),
            fees_allowance=Decimal("0.50"),
            currency="USD"
        )
        self.request = AIAActionRequest(
            request_id="req_test_01",
            client_intent="TEST_INTENT",
            target_market=MarketType.CRYPTO,
            symbol="BTC/USD",
            direction=ActionDirection.BUY,
            opportunity_ref="opp_01",
            budget=self.budget,
            max_loss=Decimal("10.00"),
            rationale="Unit test proposal",
            expiry_utc="2026-10-18T20:00:00Z",
            status=ProposalStatus.PENDING_CONFIRMATION
        )

    def test_evaluate_and_authorize_success(self):
        auth = self.governor.evaluate_and_authorize(self.request, account_id="acc1")
        self.assertTrue(auth.auth_token.startswith("auth_"))
        self.assertFalse(auth.consumed)

        # Check ledger balance locked
        bal = self.ledger.get_balance("acc1", "USD")
        self.assertEqual(bal["reserved"], Decimal("200.50"))

    def test_single_use_atomic_consumption(self):
        auth = self.governor.evaluate_and_authorize(self.request, account_id="acc1")
        consumed = self.governor.consume_authorization(auth.auth_token)
        self.assertTrue(consumed.consumed)

        # Replay attempt MUST fail
        with self.assertRaises(ReplayAuthorizationError):
            self.governor.consume_authorization(auth.auth_token)

    def test_kill_switch_blocks_authorization_and_consumption(self):
        self.governor.activate_kill_switch()
        with self.assertRaises(KillSwitchActiveError):
            self.governor.evaluate_and_authorize(self.request, account_id="acc1")

        self.governor.deactivate_kill_switch()
        auth = self.governor.evaluate_and_authorize(self.request, account_id="acc1")

        self.governor.activate_kill_switch()
        with self.assertRaises(KillSwitchActiveError):
            self.governor.consume_authorization(auth.auth_token)

    def test_high_risk_requires_user_confirmation(self):
        high_risk_budget = Budget(
            total=Decimal("1500.00"),
            principal=Decimal("1500.00"),
            currency="USD"
        )
        high_risk_req = AIAActionRequest(
            request_id="req_high_risk",
            client_intent="HIGH_RISK_TRADE",
            target_market=MarketType.CRYPTO,
            symbol="BTC/USD",
            direction=ActionDirection.BUY,
            opportunity_ref="opp_high",
            budget=high_risk_budget,
            max_loss=Decimal("75.00"),
            rationale="High capital allocation",
            expiry_utc="2026-10-18T20:00:00Z"
        )

        # Should fail without confirmation
        with self.assertRaises(GovernorError):
            self.governor.evaluate_and_authorize(high_risk_req, account_id="acc1")

        # Now supply valid confirmation
        conf = self.identity.generate_confirmation(
            user_id="user_master_01",
            request_id=high_risk_req.request_id,
            proposal_digest=high_risk_req.proposal_digest
        )
        auth = self.governor.evaluate_and_authorize(high_risk_req, account_id="acc1", user_confirmation=conf)
        self.assertIsNotNone(auth)


if __name__ == "__main__":
    unittest.main()
