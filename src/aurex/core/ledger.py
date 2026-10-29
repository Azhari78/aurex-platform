"""Global Core Ledger and Capital Reservation Engine.

Provides multi-currency double-entry ledgering, atomic capital reservation,
hash-chained audit logs, and SQLite ACID transaction persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional
import uuid

from aurex.core.models import canonical_json_bytes


class LedgerError(Exception):
    """Base error for ledger operations."""
    pass


class InsufficientFundsError(LedgerError):
    """Raised when available balance is less than requested reservation."""
    pass


class ReservationNotFoundError(LedgerError):
    """Raised when reservation ID does not exist or has already been settled."""
    pass


class GlobalLedger:
    """Institutional multi-currency ledger with atomic capital reservations."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        if not self.db_path:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Accounts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    available_balance TEXT NOT NULL,
                    reserved_balance TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (account_id, currency)
                )
            """)
            # Reservations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
                    reservation_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    settled_at_utc TEXT
                )
            """)
            # Audit journal table with hash chaining
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    action TEXT NOT NULL,
                    delta_available TEXT NOT NULL,
                    delta_reserved TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
            """)
            conn.commit()

    def _get_latest_journal_hash(self, cursor: sqlite3.Cursor) -> str:
        cursor.execute("SELECT entry_hash FROM journal_entries ORDER BY entry_id DESC LIMIT 1")
        row = cursor.fetchone()
        return row["entry_hash"] if row else "GENESIS_LEDGER_HASH"

    def deposit(self, account_id: str, currency: str, amount: Decimal, reference: str = "DEPOSIT") -> None:
        """Deposit funds into available account balance."""
        if amount <= Decimal("0"):
            raise LedgerError("Deposit amount must be strictly positive.")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT available_balance, reserved_balance FROM accounts WHERE account_id = ? AND currency = ?",
                           (account_id, currency))
            row = cursor.fetchone()
            now = datetime.now(timezone.utc).isoformat()
            if row:
                avail = Decimal(row["available_balance"]) + amount
                reserved = Decimal(row["reserved_balance"])
                cursor.execute("""
                    UPDATE accounts SET available_balance = ?, updated_at_utc = ?
                    WHERE account_id = ? AND currency = ?
                """, (str(avail), now, account_id, currency))
            else:
                avail = amount
                reserved = Decimal("0")
                cursor.execute("""
                    INSERT INTO accounts (account_id, currency, available_balance, reserved_balance, updated_at_utc)
                    VALUES (?, ?, ?, ?, ?)
                """, (account_id, currency, str(avail), str(reserved), now))

            prev_hash = self._get_latest_journal_hash(cursor)
            entry_dict = {
                "account_id": account_id,
                "currency": currency,
                "action": "DEPOSIT",
                "delta_available": str(amount),
                "delta_reserved": "0",
                "reference_id": reference,
                "prev_hash": prev_hash,
                "created_at_utc": now
            }
            entry_hash = hashlib.sha256(canonical_json_bytes(entry_dict)).hexdigest()
            cursor.execute("""
                INSERT INTO journal_entries
                (prev_hash, entry_hash, account_id, currency, action, delta_available, delta_reserved, reference_id, metadata_json, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prev_hash, entry_hash, account_id, currency, "DEPOSIT", str(amount), "0", reference, "{}", now))
            conn.commit()

    def get_balance(self, account_id: str, currency: str) -> Dict[str, Decimal]:
        """Query account balance details."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT available_balance, reserved_balance FROM accounts WHERE account_id = ? AND currency = ?",
                           (account_id, currency))
            row = cursor.fetchone()
            if not row:
                return {"available": Decimal("0"), "reserved": Decimal("0"), "total": Decimal("0")}
            avail = Decimal(row["available_balance"])
            reserved = Decimal(row["reserved_balance"])
            return {"available": avail, "reserved": reserved, "total": avail + reserved}

    def reserve(self, account_id: str, currency: str, amount: Decimal, purpose: str, request_id: str) -> str:
        """Atomically lock funds from available to reserved balance."""
        if amount <= Decimal("0"):
            raise LedgerError("Reservation amount must be strictly positive.")

        reservation_id = f"res_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT available_balance, reserved_balance FROM accounts WHERE account_id = ? AND currency = ?",
                           (account_id, currency))
            row = cursor.fetchone()
            if not row:
                raise InsufficientFundsError(f"Account {account_id} has no balance in {currency}")

            avail = Decimal(row["available_balance"])
            reserved = Decimal(row["reserved_balance"])

            if avail < amount:
                raise InsufficientFundsError(f"Insufficient available funds. Required: {amount}, Available: {avail}")

            new_avail = avail - amount
            new_reserved = reserved + amount

            cursor.execute("""
                UPDATE accounts SET available_balance = ?, reserved_balance = ?, updated_at_utc = ?
                WHERE account_id = ? AND currency = ?
            """, (str(new_avail), str(new_reserved), now, account_id, currency))

            cursor.execute("""
                INSERT INTO reservations (reservation_id, account_id, currency, amount, purpose, request_id, status, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """, (reservation_id, account_id, currency, str(amount), purpose, request_id, now))

            prev_hash = self._get_latest_journal_hash(cursor)
            entry_dict = {
                "account_id": account_id,
                "currency": currency,
                "action": "RESERVE",
                "delta_available": str(-amount),
                "delta_reserved": str(amount),
                "reference_id": reservation_id,
                "prev_hash": prev_hash,
                "created_at_utc": now
            }
            entry_hash = hashlib.sha256(canonical_json_bytes(entry_dict)).hexdigest()
            cursor.execute("""
                INSERT INTO journal_entries
                (prev_hash, entry_hash, account_id, currency, action, delta_available, delta_reserved, reference_id, metadata_json, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prev_hash, entry_hash, account_id, currency, "RESERVE", str(-amount), str(amount), reservation_id, "{}", now))
            conn.commit()

        return reservation_id

    def commit(self, reservation_id: str, actual_spent: Decimal, fees: Decimal = Decimal("0")) -> None:
        """Settle reservation: deduct spent amount, and return remainder to available balance."""
        now = datetime.now(timezone.utc).isoformat()
        total_deduction = actual_spent + fees

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT account_id, currency, amount, status FROM reservations WHERE reservation_id = ?",
                           (reservation_id,))
            res = cursor.fetchone()
            if not res:
                raise ReservationNotFoundError(f"Reservation {reservation_id} not found.")
            if res["status"] != "ACTIVE":
                raise LedgerError(f"Reservation {reservation_id} already settled ({res['status']}).")

            reserved_amount = Decimal(res["amount"])
            if total_deduction > reserved_amount:
                raise LedgerError(f"Total spent ({total_deduction}) exceeds reservation ({reserved_amount}).")

            account_id = res["account_id"]
            currency = res["currency"]
            unspent_remainder = reserved_amount - total_deduction

            cursor.execute("SELECT available_balance, reserved_balance FROM accounts WHERE account_id = ? AND currency = ?",
                           (account_id, currency))
            row = cursor.fetchone()
            avail = Decimal(row["available_balance"])
            reserved = Decimal(row["reserved_balance"])

            new_avail = avail + unspent_remainder
            new_reserved = reserved - reserved_amount

            cursor.execute("""
                UPDATE accounts SET available_balance = ?, reserved_balance = ?, updated_at_utc = ?
                WHERE account_id = ? AND currency = ?
            """, (str(new_avail), str(new_reserved), now, account_id, currency))

            cursor.execute("""
                UPDATE reservations SET status = 'COMMITTED', settled_at_utc = ?
                WHERE reservation_id = ?
            """, (now, reservation_id))

            prev_hash = self._get_latest_journal_hash(cursor)
            entry_dict = {
                "account_id": account_id,
                "currency": currency,
                "action": "COMMIT",
                "delta_available": str(unspent_remainder),
                "delta_reserved": str(-reserved_amount),
                "reference_id": reservation_id,
                "prev_hash": prev_hash,
                "created_at_utc": now
            }
            entry_hash = hashlib.sha256(canonical_json_bytes(entry_dict)).hexdigest()
            cursor.execute("""
                INSERT INTO journal_entries
                (prev_hash, entry_hash, account_id, currency, action, delta_available, delta_reserved, reference_id, metadata_json, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prev_hash, entry_hash, account_id, currency, "COMMIT", str(unspent_remainder), str(-reserved_amount), reservation_id, json.dumps({"actual_spent": str(actual_spent), "fees": str(fees)}), now))
            conn.commit()

    def release(self, reservation_id: str, reason: str = "CANCELLED") -> None:
        """Release reservation in full back to available balance."""
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT account_id, currency, amount, status FROM reservations WHERE reservation_id = ?",
                           (reservation_id,))
            res = cursor.fetchone()
            if not res:
                raise ReservationNotFoundError(f"Reservation {reservation_id} not found.")
            if res["status"] != "ACTIVE":
                raise LedgerError(f"Reservation {reservation_id} already settled ({res['status']}).")

            reserved_amount = Decimal(res["amount"])
            account_id = res["account_id"]
            currency = res["currency"]

            cursor.execute("SELECT available_balance, reserved_balance FROM accounts WHERE account_id = ? AND currency = ?",
                           (account_id, currency))
            row = cursor.fetchone()
            avail = Decimal(row["available_balance"])
            reserved = Decimal(row["reserved_balance"])

            new_avail = avail + reserved_amount
            new_reserved = reserved - reserved_amount

            cursor.execute("""
                UPDATE accounts SET available_balance = ?, reserved_balance = ?, updated_at_utc = ?
                WHERE account_id = ? AND currency = ?
            """, (str(new_avail), str(new_reserved), now, account_id, currency))

            cursor.execute("""
                UPDATE reservations SET status = 'RELEASED', settled_at_utc = ?
                WHERE reservation_id = ?
            """, (now, reservation_id))

            prev_hash = self._get_latest_journal_hash(cursor)
            entry_dict = {
                "account_id": account_id,
                "currency": currency,
                "action": "RELEASE",
                "delta_available": str(reserved_amount),
                "delta_reserved": str(-reserved_amount),
                "reference_id": reservation_id,
                "prev_hash": prev_hash,
                "created_at_utc": now
            }
            entry_hash = hashlib.sha256(canonical_json_bytes(entry_dict)).hexdigest()
            cursor.execute("""
                INSERT INTO journal_entries
                (prev_hash, entry_hash, account_id, currency, action, delta_available, delta_reserved, reference_id, metadata_json, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prev_hash, entry_hash, account_id, currency, "RELEASE", str(reserved_amount), str(-reserved_amount), reservation_id, json.dumps({"reason": reason}), now))
            conn.commit()

    def verify_audit_chain(self) -> bool:
        """Verify the integrity of the journal entries hash chain."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT entry_id, prev_hash, entry_hash, account_id, currency, action, delta_available, delta_reserved, reference_id, created_at_utc FROM journal_entries ORDER BY entry_id ASC")
            rows = cursor.fetchall()

            expected_prev = "GENESIS_LEDGER_HASH"
            for row in rows:
                if row["prev_hash"] != expected_prev:
                    return False
                entry_dict = {
                    "account_id": row["account_id"],
                    "currency": row["currency"],
                    "action": row["action"],
                    "delta_available": row["delta_available"],
                    "delta_reserved": row["delta_reserved"],
                    "reference_id": row["reference_id"],
                    "prev_hash": row["prev_hash"],
                    "created_at_utc": row["created_at_utc"]
                }
                calc_hash = hashlib.sha256(canonical_json_bytes(entry_dict)).hexdigest()
                if calc_hash != row["entry_hash"]:
                    return False
                expected_prev = row["entry_hash"]
            return True
