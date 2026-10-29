"""AUREX Core Data Models and Schema Definitions.

Implements strict decimal financial accounting, canonical hashing,
and typed contracts for AIA AI Brain, Governor, Engines, and Ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class MarketType(str, Enum):
    FX = "FX"
    CRYPTO = "CRYPTO"
    DEFI = "DEFI"


class ActionDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    LEND = "LEND"
    BORROW = "BORROW"
    PROVIDE_LIQUIDITY = "PROVIDE_LIQUIDITY"


class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_RISK = "PENDING_RISK"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


class GovernorDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"


def canonical_json_bytes(data: Dict[str, Any]) -> bytes:
    """Serialize dictionary into deterministic canonical JSON bytes."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')


def compute_sha256(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of dictionary."""
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()


class Budget(BaseModel):
    """Exact decimal budget specification."""
    total: Decimal
    principal: Decimal
    fees_allowance: Decimal = Decimal("0.0")
    gas_allowance: Decimal = Decimal("0.0")
    slippage_allowance: Decimal = Decimal("0.0")
    currency: str = "USD"

    @field_validator("total", "principal", "fees_allowance", "gas_allowance", "slippage_allowance", mode="before")
    @classmethod
    def parse_decimal(cls, v: Any) -> Decimal:
        if isinstance(v, (int, str)):
            return Decimal(str(v))
        if isinstance(v, Decimal):
            return v
        raise ValueError(f"Invalid decimal value: {v}")

    def validate_sum(self) -> bool:
        max_total = self.principal + self.fees_allowance + self.gas_allowance + self.slippage_allowance
        return self.total >= max_total


class Opportunity(BaseModel):
    """Specialist engine opportunity report."""
    opportunity_id: str
    engine_id: str
    market: MarketType
    symbol: str
    direction: ActionDirection
    confidence_score: float = Field(ge=0.0, le=1.0)
    expected_return_pct: float
    timeframe: str = "H1"
    entry_price: Decimal
    target_price: Decimal
    stop_loss: Decimal
    suggested_budget: Budget
    metrics: Dict[str, Any] = Field(default_factory=dict)
    generated_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    opportunity_digest: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.opportunity_digest:
            payload = self.model_dump(exclude={"opportunity_digest"})
            self.opportunity_digest = compute_sha256(payload)


class AIAActionRequest(BaseModel):
    """AIA Brain structured decision proposal."""
    request_id: str
    client_intent: str
    target_market: MarketType
    symbol: str
    direction: ActionDirection
    opportunity_ref: str
    budget: Budget
    max_loss: Decimal
    rationale: str
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expiry_utc: str
    proposal_digest: str = ""
    status: ProposalStatus = ProposalStatus.DRAFT

    def model_post_init(self, __context: Any) -> None:
        if not self.proposal_digest:
            payload = self.model_dump(exclude={"proposal_digest", "status"})
            self.proposal_digest = compute_sha256(payload)


class UserConfirmation(BaseModel):
    """Out-of-band user approval for high-risk proposals."""
    confirmation_id: str
    request_id: str
    proposal_digest: str
    user_id: str
    channel: str = "DASHBOARD_OOB"
    confirmed_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signature: str


class GlobalAuthorization(BaseModel):
    """Single-use atomic authorization token issued by Global Governor."""
    auth_token: str
    request_id: str
    proposal_digest: str
    reservation_id: str
    authorized_units: Decimal
    authorized_budget: Budget
    expires_at_utc: str
    consumed: bool = False
    issued_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    governor_signature: str


class ExecutionReceipt(BaseModel):
    """Execution fill receipt from Paper or live venue adapter."""
    receipt_id: str
    auth_token: str
    request_id: str
    symbol: str
    direction: ActionDirection
    executed_units: Decimal
    executed_price: Decimal
    fees_incurred: Decimal
    gas_incurred: Decimal = Decimal("0.0")
    slippage_realized: Decimal = Decimal("0.0")
    executed_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    venue: str = "PAPER_VENUE"
    reconciled: bool = False
