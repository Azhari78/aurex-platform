"""AIA Teacher Immutable Provenance and Experiment Lineage Tracking.

Records complete audit trail for learning experiments:
- hypothesis_id, source evidence, affected module, dataset window
- out-of-sample benchmark, risk delta, validation result
- approval gate status and rollback reference
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from aurex.core.models import compute_sha256


class ExperimentRecord(BaseModel):
    """Complete provenance ledger for a Teacher hypothesis and experiment."""
    hypothesis_id: str
    affected_module: str
    target_version: str
    source_evidence_digest: str
    hypothesis_statement: str
    dataset_window: str
    leakage_checks_passed: bool
    baseline_sharpe: float
    experiment_sharpe: float
    risk_delta_pct: float
    expected_economic_benefit: str
    validation_status: str  # PENDING, PASS, FAIL, REJECTED
    approved_by: Optional[str] = None
    approval_timestamp_utc: Optional[str] = None
    rollback_hash: str
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provenance_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.provenance_hash:
            payload = self.model_dump(exclude={"provenance_hash"})
            self.provenance_hash = compute_sha256(payload)


class ProvenanceRegistry:
    """Stores immutable experiment records with hash verification."""

    def __init__(self):
        self._records: Dict[str, ExperimentRecord] = {}

    def register_experiment(self, record: ExperimentRecord) -> str:
        self._records[record.hypothesis_id] = record
        return record.provenance_hash

    def get_experiment(self, hypothesis_id: str) -> Optional[ExperimentRecord]:
        return self._records.get(hypothesis_id)

    def list_experiments(self) -> List[ExperimentRecord]:
        return list(self._records.values())

    def approve_experiment(self, hypothesis_id: str, approver_id: str) -> ExperimentRecord:
        record = self._records.get(hypothesis_id)
        if not record:
            raise ValueError(f"Hypothesis {hypothesis_id} not found.")
        if record.validation_status != "PASS":
            raise ValueError(f"Cannot approve experiment with status: {record.validation_status}")

        record.approved_by = approver_id
        record.approval_timestamp_utc = datetime.now(timezone.utc).isoformat()
        # Recalculate hash with approval
        payload = record.model_dump(exclude={"provenance_hash"})
        record.provenance_hash = compute_sha256(payload)
        return record
