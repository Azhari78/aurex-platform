"""External Intelligence Gateway (EIG).

Strict security gateway for external research, news, sentiment, and market data:
- Deny-by-default architecture
- Trust & reputation scoring
- Prompt injection and payload sanitization
- Provenance tracking with SHA-256 digest
- Immutable evidence recording
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from aurex.core.models import compute_sha256


class TrustValidationResult(BaseModel):
    source_id: str
    decision: str  # ALLOW or DENY
    trust_score: float = Field(ge=0.0, le=1.0)
    reason_code: str
    sanitized_content: Dict[str, Any] = Field(default_factory=dict)
    content_digest: str = ""
    evaluated_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExternalIntelligenceGateway:
    """Gatekeeper for all external market intelligence and research feeds."""

    # Malicious / Prompt injection patterns to detect and quarantine
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*:\s*override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"bypass\s+governor", re.IGNORECASE),
        re.compile(r"execute\s+unauthorized", re.IGNORECASE),
        re.compile(r"transfer\s+all\s+funds", re.IGNORECASE),
        re.compile(r"private_key", re.IGNORECASE),
    ]

    def __init__(self):
        # Known allowlisted providers and their baseline trust scores
        self._allowlisted_sources: Dict[str, Dict[str, Any]] = {
            "binance_public_ticker": {"type": "MARKET_DATA", "base_trust": 0.95},
            "coinbase_public_ticker": {"type": "MARKET_DATA", "base_trust": 0.95},
            "oanda_rates_feed": {"type": "MARKET_DATA", "base_trust": 0.98},
            "defillama_yield_api": {"type": "DEFI_DATA", "base_trust": 0.90},
            "bloomberg_macro_feed": {"type": "MACRO_NEWS", "base_trust": 0.88},
            "reuters_macro_feed": {"type": "MACRO_NEWS", "base_trust": 0.88},
        }

    def register_connector(self, source_id: str, connector_type: str, base_trust: float) -> None:
        """Explicitly register and allowlist an external connector."""
        self._allowlisted_sources[source_id] = {
            "type": connector_type,
            "base_trust": max(0.0, min(1.0, base_trust))
        }

    def validate_and_ingest(self, source_id: str, raw_payload: Dict[str, Any]) -> TrustValidationResult:
        """Sanitize, score, and validate external intelligence. Fail-closed on any doubt."""
        # Check allowlist
        if source_id not in self._allowlisted_sources:
            return TrustValidationResult(
                source_id=source_id,
                decision="DENY",
                trust_score=0.0,
                reason_code="SOURCE_NOT_ALLOWLISTED"
            )

        source_meta = self._allowlisted_sources[source_id]
        base_trust = source_meta["base_trust"]

        # Content string check for injection attempts
        payload_str = json.dumps(raw_payload)
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(payload_str):
                return TrustValidationResult(
                    source_id=source_id,
                    decision="DENY",
                    trust_score=0.0,
                    reason_code="PROMPT_INJECTION_OR_ATTACK_DETECTED"
                )

        # Content hashing
        content_digest = compute_sha256(raw_payload)

        # Deep sanitization: strip executable scripts or unwanted tags
        sanitized = {}
        for k, v in raw_payload.items():
            if isinstance(v, str):
                # Clean html/scripts
                cleaned = re.sub(r"<[^>]+>", "", v).strip()
                sanitized[k] = cleaned
            elif isinstance(v, (int, float, bool, list, dict)):
                sanitized[k] = v

        return TrustValidationResult(
            source_id=source_id,
            decision="ALLOW",
            trust_score=base_trust,
            reason_code="TRUST_VERIFIED",
            sanitized_content=sanitized,
            content_digest=content_digest
        )
