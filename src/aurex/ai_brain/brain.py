"""AIA AI Brain Central Cognitive Orchestration Runtime.

Responsible for:
- Orchestrating specialist engines (FX, Crypto, DeFi)
- Interfacing with EIG for external market context
- Evaluating trade-offs across markets
- Synthesizing rationale and structured Decision Proposals (AIAActionRequest)
- Strictly bounded: Cannot sign transactions or execute orders directly!
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
import uuid

from aurex.ai_brain.eig import ExternalIntelligenceGateway
from aurex.core.models import (
    AIAActionRequest,
    MarketType,
    Opportunity,
    ProposalStatus,
    compute_sha256,
)
from aurex.economics.evaluator import EconomicsAuthority
from aurex.engines.base import BaseSpecialistEngine
from aurex.risk.manager import RiskManager


class AIABrain:
    """The central cognitive orchestration agent of AUREX."""

    def __init__(
        self,
        engines: List[BaseSpecialistEngine],
        economics: EconomicsAuthority,
        risk: RiskManager,
        eig: ExternalIntelligenceGateway
    ):
        self.engines = {e.market_type: e for e in engines}
        self.economics = economics
        self.risk = risk
        self.eig = eig
        self.active_proposals: Dict[str, AIAActionRequest] = {}
        self.rejected_proposals: Dict[str, Dict[str, str]] = {}
        self.explanation_log: List[Dict[str, str]] = []

    def scan_all_markets(self) -> Dict[MarketType, List[Opportunity]]:
        """Query all active specialist engines for live opportunities."""
        results = {}
        for market, engine in self.engines.items():
            try:
                opps = engine.scan_opportunities()
                results[market] = opps
            except Exception as e:
                results[market] = []
        return results

    def deliberate_and_propose(self, client_intent: str = "MAXIMIZE_RISK_ADJUSTED_YIELD") -> List[AIAActionRequest]:
        """Cognitive cycle:
        1. Scan opportunities from FX, Crypto, DeFi
        2. Filter through Economics Authority (EV and R:R)
        3. Filter through Risk & Capital Manager
        4. Synthesize Decision Proposals with transparent rationale
        """
        all_market_opps = self.scan_all_markets()
        candidate_opps: List[Opportunity] = []
        for opp_list in all_market_opps.values():
            candidate_opps.extend(opp_list)

        # Sort candidate opportunities by confidence and expected return
        candidate_opps.sort(key=lambda o: (o.confidence_score, o.expected_return_pct), reverse=True)

        generated_proposals = []

        for opp in candidate_opps:
            # 1. Economic Viability Gate
            econ_verdict = self.economics.evaluate(opp)
            if not econ_verdict.viable:
                self.rejected_proposals[opp.opportunity_id] = {
                    "stage": "ECONOMICS",
                    "reason": econ_verdict.reason,
                    "symbol": opp.symbol
                }
                continue

            # Build draft action request
            request_id = f"req_{uuid.uuid4().hex[:10]}"
            now_dt = datetime.now(timezone.utc)
            expiry_dt = now_dt + timedelta(minutes=30)

            # Rationale explanation
            rationale = (
                f"AIA Brain identified {opp.market.value} opportunity on {opp.symbol} "
                f"({opp.direction.value}) with {opp.confidence_score*100:.1f}% model confidence. "
                f"Economics verified net EV of +{econ_verdict.net_ev_pct:.2f}% (R:R {econ_verdict.risk_reward_ratio:.2f}). "
                f"Timeframe: {opp.timeframe}. Target: {opp.target_price}, Stop: {opp.stop_loss}."
            )

            max_loss = opp.suggested_budget.principal * Decimal("0.05")  # 5% max budget loss

            draft_proposal = AIAActionRequest(
                request_id=request_id,
                client_intent=client_intent,
                target_market=opp.market,
                symbol=opp.symbol,
                direction=opp.direction,
                opportunity_ref=opp.opportunity_id,
                budget=opp.suggested_budget,
                max_loss=max_loss,
                rationale=rationale,
                expiry_utc=expiry_dt.isoformat(),
                status=ProposalStatus.DRAFT
            )

            # 2. Risk & Capital Gate
            risk_verdict = self.risk.evaluate_proposal(draft_proposal)
            if not risk_verdict.approved:
                self.rejected_proposals[opp.opportunity_id] = {
                    "stage": "RISK",
                    "reason": risk_verdict.reason,
                    "symbol": opp.symbol
                }
                continue

            # Mark proposal ready for approval / authorization
            draft_proposal.status = ProposalStatus.PENDING_CONFIRMATION
            self.active_proposals[draft_proposal.request_id] = draft_proposal
            generated_proposals.append(draft_proposal)

            self.explanation_log.append({
                "request_id": draft_proposal.request_id,
                "symbol": draft_proposal.symbol,
                "market": draft_proposal.target_market.value,
                "rationale": rationale,
                "timestamp": now_dt.isoformat()
            })

        return generated_proposals

    def get_proposal_status(self, request_id: str) -> Optional[AIAActionRequest]:
        return self.active_proposals.get(request_id)
