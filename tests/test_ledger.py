"""Unit tests for Global Core Ledger and Capital Reservations."""

from decimal import Decimal
import unittest
from aurex.core.ledger import (
    GlobalLedger,
    InsufficientFundsError,
    LedgerError,
    ReservationNotFoundError,
)


class TestGlobalLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = GlobalLedger()

    def test_deposit_and_balance_query(self):
        self.ledger.deposit("acc1", "USD", Decimal("500.00"))
        bal = self.ledger.get_balance("acc1", "USD")
        self.assertEqual(bal["available"], Decimal("500.00"))
        self.assertEqual(bal["reserved"], Decimal("0.00"))
        self.assertEqual(bal["total"], Decimal("500.00"))

    def test_reserve_funds_success(self):
        self.ledger.deposit("acc1", "USD", Decimal("1000.00"))
        res_id = self.ledger.reserve("acc1", "USD", Decimal("300.00"), purpose="CRYPTO:BUY", request_id="req1")
        self.assertTrue(res_id.startswith("res_"))

        bal = self.ledger.get_balance("acc1", "USD")
        self.assertEqual(bal["available"], Decimal("700.00"))
        self.assertEqual(bal["reserved"], Decimal("300.00"))
        self.assertEqual(bal["total"], Decimal("1000.00"))

    def test_reserve_insufficient_funds_rejected(self):
        self.ledger.deposit("acc1", "USD", Decimal("100.00"))
        with self.assertRaises(InsufficientFundsError):
            self.ledger.reserve("acc1", "USD", Decimal("150.00"), purpose="CRYPTO:BUY", request_id="req2")

    def test_commit_reservation_with_remainder(self):
        self.ledger.deposit("acc1", "USD", Decimal("1000.00"))
        res_id = self.ledger.reserve("acc1", "USD", Decimal("400.00"), purpose="CRYPTO:BUY", request_id="req3")

        # Spend 350 + 5 fees, 45 released back
        self.ledger.commit(res_id, actual_spent=Decimal("350.00"), fees=Decimal("5.00"))

        bal = self.ledger.get_balance("acc1", "USD")
        self.assertEqual(bal["available"], Decimal("645.00"))
        self.assertEqual(bal["reserved"], Decimal("0.00"))
        self.assertEqual(bal["total"], Decimal("645.00"))

    def test_release_reservation(self):
        self.ledger.deposit("acc1", "USD", Decimal("500.00"))
        res_id = self.ledger.reserve("acc1", "USD", Decimal("200.00"), purpose="DEFI:LEND", request_id="req4")
        self.ledger.release(res_id, reason="EXPIRED")

        bal = self.ledger.get_balance("acc1", "USD")
        self.assertEqual(bal["available"], Decimal("500.00"))
        self.assertEqual(bal["reserved"], Decimal("0.00"))

    def test_audit_hash_chain_integrity(self):
        self.ledger.deposit("acc1", "USD", Decimal("1000.00"))
        res_id = self.ledger.reserve("acc1", "USD", Decimal("250.00"), purpose="FX:BUY", request_id="req5")
        self.ledger.commit(res_id, actual_spent=Decimal("240.00"), fees=Decimal("1.00"))
        self.assertTrue(self.ledger.verify_audit_chain())


if __name__ == "__main__":
    unittest.main()
