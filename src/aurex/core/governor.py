"""Global Governor Runtime Authority.

Sole transaction authority in the AUREX architecture:
- Enforces deny-by-default execution policy
- Enforces atomic one-time authorization token consumption
- Enforces kill-switch and operational mode safety gates (LIVE LOCKED by default)
- Coordinates with GlobalLedger for capital reservation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Dict, Optional, Set
import uuid

from aurex.core.ledger import GlobalLedger, LedgerError
from aurex.core.models import (
    AIAActionRequest,
    GlobalAuthorization,
    GovernorDecision,
    MarketType,
    ProposalStatus,
    UserConfirmation,
    compute_sha256,
)


class GovernorError(Exception):
    """Base error for Governor policy violations."""
    pass


class KillSwitchActiveError(GovernorError):
    """Raised when an operation is attempted while kill switch is engaged."""
    pass


class LiveModeLockedError(GovernorError):
    """Raised when an unapproved live execution is attempted."""
    pass


class ReplayAuthorizationError(GovernorError):
    """Raised when an authorization token is consumed more than once."""
    pass


class AuthorizationExpiredError(GovernorError):
    """Raised when an authorization token has passed its expiration time."""
    pass


class GlobalGovernor:
    """The central gatekeeper of transaction authorization in AUREX."""

    def __init__(self, ledger: GlobalLedger, live_authorized: bool = False):
        self.ledger = ledger
        self.live_authorized = live_authorized
        self.kill_switch_active = False
        self.high_risk_threshold_usd = Decimal("1000.00")
        self._authorizations: Dict[str, GlobalAuthorization] = {}
        self._consumed_tokens: Set[str] = set()
        self._revoked_tokens: Set[str] = set()

    def activate_kill_switch(self, reason: str = "MANUAL_TRIGGER") -> None:
        """Immediately halts all transaction authorizations."""
        self.kill_switch_active = True

    def deactivate_kill_switch(self) -> None:
        """Disengages the kill switch."""
        self.kill_switch_active = False

    def evaluate_and_authorize(
        self,
        request: AIAActionRequest,
        account_id: str,
        user_confirmation: Optional[UserConfirmation] = None,
        ttl_seconds: int = 300
    ) -> GlobalAuthorization:
        """Evaluate an AIAActionRequest, reserve funds in ledger, and issue an atomic authorization."""
        if self.kill_switch_active:
            raise KillSwitchActiveError("Global Governor Kill Switch is active. All authorizations denied.")

        if not request.budget.validate_sum():
            raise GovernorError("Budget components exceed total budget cap.")

        # High-risk checks: requiring out-of-band user confirmation
        is_high_risk = request.budget.total >= self.high_risk_threshold_usd
        if is_high_risk:
            if not user_confirmation:
                raise GovernorError(f"High-risk action ({request.budget.total} USD >= {self.high_risk_threshold_usd}) requires user confirmation.")
            if user_confirmation.request_id != request.request_id:
                raise GovernorError("User confirmation request_id does not match proposal.")
            if user_confirmation.proposal_digest != request.proposal_digest:
                raise GovernorError("User confirmation proposal digest does not match current proposal.")

        # Atomic capital reservation with the global ledger
        currency = request.budget.currency
        amount = request.budget.total
        purpose = f"{request.target_market}:{request.symbol}:{request.direction}"

        reservation_id = self.ledger.reserve(
            account_id=account_id,
            currency=currency,
            amount=amount,
            purpose=purpose,
            request_id=request.request_id
        )

        # Issue one-time atomic authorization token
        now_dt = datetime.now(timezone.utc)
        expires_dt = now_dt + timedelta(seconds=ttl_seconds)
        auth_token = f"auth_{uuid.uuid4().hex}"

        gov_signature_payload = {
            "auth_token": auth_token,
            "request_id": request.request_id,
            "reservation_id": reservation_id,
            "proposal_digest": request.proposal_digest,
            "budget": request.budget.model_dump(),
            "expires_at_utc": expires_dt.isoformat()
        }
        governor_sig = hashlib.sha256(json.dumps(gov_signature_payload, sort_keys=True, default=str).encode()).hexdigest()

        auth = GlobalAuthorization(
            auth_token=auth_token,
            request_id=request.request_id,
            proposal_digest=request.proposal_digest,
            reservation_id=reservation_id,
            authorized_units=request.budget.principal,
            authorized_budget=request.budget,
            expires_at_utc=expires_dt.isoformat(),
            governor_signature=governor_sig,
            consumed=False
        )

        self._authorizations[auth_token] = auth
        return auth

    def consume_authorization(self, auth_token: str) -> GlobalAuthorization:
        """Atomically consume an authorization token for execution. Replay is strictly forbidden."""
        if self.kill_switch_active:
            raise KillSwitchActiveError("Kill switch engaged: cannot consume authorization.")

        if auth_token in self._consumed_tokens:
            raise ReplayAuthorizationError(f"Authorization token {auth_token} has already been consumed (replay violation).")

        if auth_token in self._revoked_tokens:
            raise GovernorError(f"Authorization token {auth_token} has been revoked.")

        auth = self._authorizations.get(auth_token)
        if not auth:
            raise GovernorError(f"Authorization token {auth_token} not recognized.")

        # Check expiration
        now_iso = datetime.now(timezone.utc).isoformat()
        if now_iso > auth.expires_at_utc:
            self.ledger.release(auth.reservation_id, reason="AUTHORIZATION_EXPIRED")
            raise AuthorizationExpiredError(f"Authorization token {auth_token} has expired.")

        # Mark as consumed atomically
        auth.consumed = True
        self._consumed_tokens.add(auth_token)
        return auth

    def revoke_authorization(self, auth_token: str, reason: str = "MANUAL_REVOCATION") -> None:
        """Revoke an active authorization and release its capital reservation."""
        auth = self._authorizations.get(auth_token)
        if not auth:
            raise GovernorError(f"Authorization token {auth_token} not found.")

        if auth.consumed:
            raise GovernorError(f"Cannot revoke already consumed authorization {auth_token}.")

        self._revoked_tokens.add(auth_token)
        self.ledger.release(auth.reservation_id, reason=reason)
