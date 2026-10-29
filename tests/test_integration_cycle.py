"""End-to-End integration test covering the complete AUREX execution cycle."""

from decimal import Decimal
import unittest
from aurex.ai_brain.brain import AIABrain
from aurex.ai_brain.eig import ExternalIntelligenceGateway
from aurex.core.governor import GlobalGovernor
from aurex.core.identity import IdentityManager
from aurex.core.ledger import GlobalLedger
from aurex.economics.evaluator import EconomicsAuthority
from aurex.engines.crypto import CryptoTradingEngine
from aurex.engines.defi import DeFiEngine
from aurex.engines.fx import FXTradingEngine
from aurex.execution.paper_broker import PaperBroker
from aurex.execution.reconciliation import ReconciliationEngine
from aurex.risk.manager import RiskManager


class TestEndToEndExecutionCycle(unittest.TestCase):
    def setUp(self):
        self.ledger = GlobalLedger()
        self.ledger.deposit("account_main", "USD", Decimal("10000.00"), reference="TEST_DEPOSIT")
        self.governor = GlobalGovernor(ledger=self.ledger)
        self.identity = IdentityManager()
        self.risk = RiskManager(portfolio_capital=Decimal("10000.00"))
        self.economics = EconomicsAuthority()
        self.eig = ExternalIntelligenceGateway()

        self.crypto_engine = CryptoTradingEngine()
        self.fx_engine = FXTradingEngine()
        self.defi_engine = DeFiEngine()

        self.brain = AIABrain(
            engines=[self.crypto_engine, self.fx_engine, self.defi_engine],
            economics=self.economics,
            risk=self.risk,
            eig=self.eig
        )

        self.broker = PaperBroker(governor=self.governor, ledger=self.ledger)
        self.reconciler = ReconciliationEngine(ledger=self.ledger)

    def test_complete_autonomous_pipeline(self):
        # 1. Scan and deliberate
        proposals = self.brain.deliberate_and_propose()
        self.assertGreater(len(proposals), 0)

        proposal = proposals[0]

        # 2. Authorize via Governor
        auth = self.governor.evaluate_and_authorize(
            request=proposal,
            account_id="account_main"
        )
        self.assertIsNotNone(auth.auth_token)

        # Verify ledger has reserved the budget
        bal = self.ledger.get_balance("account_main", "USD")
        self.assertEqual(bal["reserved"], proposal.budget.total)

        # 3. Paper execution
        price = Decimal("2650.00") if "ETH" in proposal.symbol else Decimal("1.00")
        receipt = self.broker.execute_order(auth, proposal, current_market_price=price)
        self.assertIsNotNone(receipt.receipt_id)
        self.assertGreater(receipt.executed_units, Decimal("0"))

        # Verify ledger reservation committed
        bal_after = self.ledger.get_balance("account_main", "USD")
        self.assertEqual(bal_after["reserved"], Decimal("0.00"))

        # 4. Reconciliation
        report = self.reconciler.reconcile_receipts([receipt])
        self.assertTrue(report.is_clean)
        self.assertEqual(report.reconciled_count, 1)

        # 5. Audit Chain Integrity
        self.assertTrue(self.ledger.verify_audit_chain())


if __name__ == "__main__":
    unittest.main()
