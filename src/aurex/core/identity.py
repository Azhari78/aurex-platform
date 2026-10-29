"""Identity, Entitlements, and Independent User Confirmation.

Provides role-based access control (RBAC), out-of-band user confirmation
verification with HMAC-SHA256 signatures, nonce anti-replay, and revocation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from typing import Dict, List, Optional, Set
import uuid

from aurex.core.models import UserConfirmation, compute_sha256


class IdentityError(Exception):
    """Base error for identity and confirmation operations."""
    pass


class ReplayConfirmationError(IdentityError):
    """Raised when a confirmation nonce/token is reused."""
    pass


class InvalidSignatureError(IdentityError):
    """Raised when user signature fails cryptographic verification."""
    pass


class IdentityManager:
    """Manages system users, authentication keys, and approval entitlements."""

    def __init__(self):
        self._users: Dict[str, Dict[str, str]] = {}
        self._user_secrets: Dict[str, str] = {}
        self._used_nonces: Set[str] = set()
        self._revoked_confirmations: Set[str] = set()
        self._init_default_admin()

    def _init_default_admin(self) -> None:
        default_user = "user_master_01"
        default_secret = secrets.token_hex(32)
        self.register_user(
            user_id=default_user,
            role="TRADER_OFFICER",
            secret_key=default_secret,
            display_name="Master Account Operator"
        )

    def register_user(self, user_id: str, role: str, secret_key: str, display_name: str) -> None:
        """Register a new user with cryptographic credentials."""
        self._users[user_id] = {
            "user_id": user_id,
            "role": role,
            "display_name": display_name,
            "created_at_utc": datetime.now(timezone.utc).isoformat()
        }
        self._user_secrets[user_id] = secret_key

    def get_user_secret(self, user_id: str) -> Optional[str]:
        return self._user_secrets.get(user_id)

    def generate_confirmation(
        self,
        user_id: str,
        request_id: str,
        proposal_digest: str,
        channel: str = "DASHBOARD_OOB"
    ) -> UserConfirmation:
        """Helper to create a cryptographically signed UserConfirmation for testing and authorized approvals."""
        secret = self._user_secrets.get(user_id)
        if not secret:
            raise IdentityError(f"User {user_id} not registered.")

        confirmation_id = f"conf_{uuid.uuid4().hex}"
        now_iso = datetime.now(timezone.utc).isoformat()
        msg_payload = f"{confirmation_id}:{request_id}:{proposal_digest}:{user_id}:{now_iso}"
        signature = hmac.new(secret.encode(), msg_payload.encode(), hashlib.sha256).hexdigest()

        return UserConfirmation(
            confirmation_id=confirmation_id,
            request_id=request_id,
            proposal_digest=proposal_digest,
            user_id=user_id,
            channel=channel,
            confirmed_at_utc=now_iso,
            signature=signature
        )

    def verify_confirmation(self, confirmation: UserConfirmation) -> bool:
        """Cryptographically verify out-of-band user approval and prevent replay."""
        if confirmation.confirmation_id in self._used_nonces:
            raise ReplayConfirmationError(f"Confirmation {confirmation.confirmation_id} already consumed.")

        if confirmation.confirmation_id in self._revoked_confirmations:
            raise IdentityError(f"Confirmation {confirmation.confirmation_id} has been revoked.")

        secret = self._user_secrets.get(confirmation.user_id)
        if not secret:
            raise IdentityError(f"User {confirmation.user_id} not registered.")

        msg_payload = f"{confirmation.confirmation_id}:{confirmation.request_id}:{confirmation.proposal_digest}:{confirmation.user_id}:{confirmation.confirmed_at_utc}"
        expected_sig = hmac.new(secret.encode(), msg_payload.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(confirmation.signature, expected_sig):
            raise InvalidSignatureError("Signature mismatch: confirmation not authentic.")

        self._used_nonces.add(confirmation.confirmation_id)
        return True

    def revoke_confirmation(self, confirmation_id: str) -> None:
        """Mark a confirmation as revoked."""
        self._revoked_confirmations.add(confirmation_id)
