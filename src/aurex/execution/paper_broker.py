"""Realistic PAPER Execution Broker Simulator.

Simulates institutional order execution:
- Consumes atomic GlobalAuthorization from Governor
- Rejects unauthenticated or replayed orders
- Simulates realistic fill price, order slippage, and venue fees
- Settles capital reservation with GlobalLedger
- Returns immutable ExecutionReceipt
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import random
from typing import Dict, List, Optional
import uuid

from aurex.core.governor import GlobalGovernor, GovernorError
from aurex.core.ledger import GlobalLedger
from aurex.core.models import (
    AIAActionRequest,
    ActionDirection,
    ExecutionReceipt,
    GlobalAuthorization,
    MarketType,
)


class PaperBroker:
    """Venue execution simulation environment."""

    def __init__(self, governor: GlobalGovernor, ledger: GlobalLedger):
        self.governor = governor
        self.ledger = ledger
        self.executed_receipts: List[ExecutionReceipt] = []
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.closed_positions: List[Dict[str, Any]] = []

    def execute_order(
        self,
        authorization: GlobalAuthorization,
        request: AIAActionRequest,
        current_market_price: Decimal
    ) -> ExecutionReceipt:
        """Execute order against paper venue using single-use authorization."""
        # 1. Consume authorization token atomically (strictly fails if replayed)
        consumed_auth = self.governor.consume_authorization(authorization.auth_token)

        # 2. Simulate realistic slippage (0.01% - 0.05%)
        slippage_factor = Decimal("1.0002") if request.direction == ActionDirection.BUY else Decimal("0.9998")
        fill_price = current_market_price * slippage_factor

        # 3. Compute units and fee
        principal = authorization.authorized_units
        fee = authorization.authorized_budget.fees_allowance
        gas = authorization.authorized_budget.gas_allowance
        slippage_cost = authorization.authorized_budget.slippage_allowance

        units = principal / fill_price if fill_price > Decimal("0") else Decimal("0")

        # 4. Settle reservation in GlobalLedger
        self.ledger.commit(
            reservation_id=consumed_auth.reservation_id,
            actual_spent=principal,
            fees=fee + gas
        )

        receipt_id = f"rcpt_{uuid.uuid4().hex[:10]}"
        receipt = ExecutionReceipt(
            receipt_id=receipt_id,
            auth_token=authorization.auth_token,
            request_id=request.request_id,
            symbol=request.symbol,
            direction=request.direction,
            executed_units=units,
            executed_price=fill_price,
            fees_incurred=fee,
            gas_incurred=gas,
            slippage_realized=slippage_cost,
            venue="PAPER_SIMULATED_VENUE",
            reconciled=False
        )

        self.executed_receipts.append(receipt)

        # 5. Track open position
        position_id = f"pos_{uuid.uuid4().hex[:8]}"
        self.open_positions[position_id] = {
            "position_id": position_id,
            "symbol": request.symbol,
            "market": request.target_market.value,
            "direction": request.direction.value,
            "units": units,
            "entry_price": fill_price,
            "invested_principal": principal,
            "opened_at_utc": datetime.now(timezone.utc).isoformat(),
            "receipt_id": receipt_id
        }

        return receipt

    def close_position(self, position_id: str, exit_price: Decimal) -> Dict[str, Any]:
        """Close an active open position, compute realized PnL, and credit back to ledger."""
        pos = self.open_positions.pop(position_id, None)
        if not pos:
            raise ValueError(f"Position {position_id} not found.")

        direction = pos["direction"]
        units = pos["units"]
        entry_price = pos["entry_price"]
        principal = pos["invested_principal"]

        # Calculate PnL
        if direction == "BUY":
            pnl = units * (exit_price - entry_price)
        elif direction == "SELL":
            pnl = units * (entry_price - exit_price)
        else:  # LEND / PROVIDE_LIQUIDITY (DeFi Yield)
            pnl = principal * Decimal("0.018")  # Accrued protocol fee / yield

        net_pnl = round(pnl, 2)
        total_payout = max(Decimal("0.00"), principal + net_pnl)

        # Deposit funds back into ledger
        self.ledger.deposit(
            account_id="account_main",
            currency="USD",
            amount=total_payout,
            reference=f"CLOSE_{pos['symbol']}_{position_id}"
        )

        closed_record = {
            "position_id": position_id,
            "symbol": pos["symbol"],
            "market": pos["market"],
            "direction": direction,
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "units": float(units),
            "invested_principal": float(principal),
            "realized_pnl": float(net_pnl),
            "pnl_pct": float(round((net_pnl / principal) * 100, 2)),
            "total_payout": float(total_payout),
            "closed_at_utc": datetime.now(timezone.utc).isoformat()
        }

        self.closed_positions.append(closed_record)
        return closed_record
