"""AUREX Master Platform Command-Line Interface (CLI).

Provides commands to operate, inspect, scan, authorize, and run paper trades:
  python -m aurex.cli status
  python -m aurex.cli scan
  python -m aurex.cli run-cycle
  python -m aurex.cli teacher-cycle
  python -m aurex.cli serve
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
import sys
from typing import Optional

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
from aurex.teacher.provenance import ProvenanceRegistry
from aurex.teacher.supervisor import AIATeacherSupervisor


def setup_system():
    """Bootstrap complete institutional system instances."""
    ledger = GlobalLedger()
    # Deposit initial testing capital
    ledger.deposit("account_main", "USD", Decimal("10000.00"), reference="INITIAL_FUNDING_USD")
    ledger.deposit("account_main", "MYR", Decimal("25000.00"), reference="INITIAL_FUNDING_MYR")

    governor = GlobalGovernor(ledger=ledger, live_authorized=False)
    governor.high_risk_threshold_usd = Decimal("5000.00")
    identity = IdentityManager()
    risk = RiskManager(portfolio_capital=Decimal("50000.00"))
    economics = EconomicsAuthority()
    eig = ExternalIntelligenceGateway()

    crypto_engine = CryptoTradingEngine()
    fx_engine = FXTradingEngine()
    defi_engine = DeFiEngine()

    brain = AIABrain(
        engines=[crypto_engine, fx_engine, defi_engine],
        economics=economics,
        risk=risk,
        eig=eig
    )

    provenance = ProvenanceRegistry()
    teacher = AIATeacherSupervisor(provenance)
    broker = PaperBroker(governor=governor, ledger=ledger)
    reconciler = ReconciliationEngine(ledger=ledger)

    return {
        "ledger": ledger,
        "governor": governor,
        "identity": identity,
        "risk": risk,
        "economics": economics,
        "eig": eig,
        "brain": brain,
        "provenance": provenance,
        "teacher": teacher,
        "broker": broker,
        "reconciler": reconciler,
        "engines": {
            "crypto": crypto_engine,
            "fx": fx_engine,
            "defi": defi_engine
        }
    }


def cmd_status(ctx):
    print("================================================================================")
    print("                      AUREX MASTER PLATFORM v1.3.1                              ")
    print("             Institutional Multi-Market Algorithmic Trading                     ")
    print("================================================================================")
    gov = ctx["governor"]
    ledger = ctx["ledger"]
    balance_usd = ledger.get_balance("account_main", "USD")
    balance_myr = ledger.get_balance("account_main", "MYR")

    print(f"Governance Mode  : PAPER SIMULATION (LIVE: LOCKED)")
    print(f"Kill Switch      : {'ENGAGED (HALTED)' if gov.kill_switch_active else 'DISENGAGED (NORMAL)'}")
    print(f"Global Ledger    : USD Available: ${balance_usd['available']} | Reserved: ${balance_usd['reserved']} | Total: ${balance_usd['total']}")
    print(f"                   MYR Available: RM{balance_myr['available']} | Reserved: RM{balance_myr['reserved']}")
    print(f"Audit Chain Integrity: {'VERIFIED [OK]' if ledger.verify_audit_chain() else 'CORRUPTED [FAIL]'}")
    print(f"Active Engines   : FX MHE, Crypto Trading Engine, Multi-chain DeFi")
    print("================================================================================")


def cmd_scan(ctx):
    cmd_status(ctx)
    print("\nScanning all markets (FX, Crypto, DeFi) with AIA Brain...")
    brain = ctx["brain"]
    proposals = brain.deliberate_and_propose()

    print(f"\nGenerated {len(proposals)} Qualified Decision Proposals:")
    for i, p in enumerate(proposals, 1):
        print(f"\n[{i}] Request ID : {p.request_id}")
        print(f"    Market     : {p.target_market.value} | Symbol: {p.symbol} | Direction: {p.direction.value}")
        print(f"    Budget     : Principal: ${p.budget.principal} (Total Cap: ${p.budget.total})")
        print(f"    Rationale  : {p.rationale}")
        print(f"    Status     : {p.status.value}")
        print(f"    Digest     : {p.proposal_digest[:16]}...")


def cmd_run_cycle(ctx):
    cmd_status(ctx)
    print("\nExecuting Complete Autonomous Cycle (Scan -> Propose -> Authorize -> Execute -> Reconcile)...")
    brain = ctx["brain"]
    governor = ctx["governor"]
    broker = ctx["broker"]
    reconciler = ctx["reconciler"]
    identity = ctx["identity"]

    proposals = brain.deliberate_and_propose()
    if not proposals:
        print("No proposals generated meeting strict economic and risk requirements.")
        return

    proposal = proposals[0]
    print(f"\nSelected Candidate Proposal: {proposal.symbol} ({proposal.target_market.value})")
    print(f"Rationale: {proposal.rationale}")

    # Generate user confirmation if needed
    user_conf = None
    if proposal.budget.total >= governor.high_risk_threshold_usd:
        print("High risk proposal detected. Generating cryptographic Out-Of-Band Confirmation...")
        user_conf = identity.generate_confirmation(
            user_id="user_master_01",
            request_id=proposal.request_id,
            proposal_digest=proposal.proposal_digest
        )

    print("\n[Step 1] Requesting Global Governor Authorization...")
    auth = governor.evaluate_and_authorize(
        request=proposal,
        account_id="account_main",
        user_confirmation=user_conf
    )
    print(f"  -> Authorization Granted! Auth Token: {auth.auth_token}")
    print(f"  -> Capital Reserved in Ledger: Reservation ID: {auth.reservation_id}")

    print("\n[Step 2] Executing order via Paper Broker...")
    entry_price = Decimal("68500.00") if "BTC" in proposal.symbol else (Decimal("1.0850") if "EUR" in proposal.symbol else Decimal("1.00"))
    receipt = broker.execute_order(auth, proposal, entry_price)
    print(f"  -> Execution Fill Confirmed! Receipt ID: {receipt.receipt_id}")
    print(f"  -> Executed Units: {receipt.executed_units:.6f} at ${receipt.executed_price:.4f}")
    print(f"  -> Fees: ${receipt.fees_incurred} | Slippage: ${receipt.slippage_realized}")

    print("\n[Step 3] Running Authoritative Reconciliation...")
    report = reconciler.reconcile_receipts([receipt])
    print(f"  -> Reconciliation Result: {'CLEAN [PASS]' if report.is_clean else 'DISCREPANCIES DETECTED [FAIL]'}")
    print(f"  -> Total Reconciled: {report.reconciled_count}/{report.total_receipts}")

    balance = ctx["ledger"].get_balance("account_main", "USD")
    print(f"\nFinal Account Balance: Available: ${balance['available']} | Reserved: ${balance['reserved']} | Total: ${balance['total']}")
    print("================================================================================")


def cmd_teacher_cycle(ctx):
    print("================================================================================")
    print("                   AIA TEACHER CONTROLLED LEARNING CYCLE                        ")
    print("================================================================================")
    teacher = ctx["teacher"]
    provenance = ctx["provenance"]

    # Sample trade history for observation
    sample_trades = [
        {"profit": 15.2, "slippage": 1.2},
        {"profit": -8.4, "slippage": 2.1},
        {"profit": 22.0, "slippage": 0.8},
        {"profit": -12.0, "slippage": 4.5},
        {"profit": 18.5, "slippage": 1.5},
    ]

    print("[Step 1: OBSERVE] Observing recent execution performance on Crypto Engine...")
    obs = teacher.observe_performance("ENGINE_CRYPTO_SPOT_V1", sample_trades)
    print(f"  -> Win Rate: {obs['win_rate_pct']}% | Avg Slippage: {obs['avg_slippage_bps']} bps")

    print("\n[Step 2: DIAGNOSE] Analyzing potential model weakness...")
    diag = teacher.diagnose_weakness(obs)
    print(f"  -> Issue: {diag['identified_issue']} | Recommendation: {diag['recommended_action']}")

    print("\n[Step 3 & 4: HYPOTHESIS & PROVENANCE] Formulating testable improvement...")
    record = teacher.formulate_hypothesis(
        diagnosis=diag,
        hypothesis_statement="Incorporate adaptive dynamic spread threshold to avoid choppy false breakouts.",
        affected_module="aurex.engines.crypto"
    )
    print(f"  -> Hypothesis ID: {record.hypothesis_id}")
    print(f"  -> Provenance Digest: {record.provenance_hash[:20]}...")

    print("\n[Step 5 & 6: SANDBOX EXPERIMENT & DIGITAL TWIN] Running backtest simulation...")
    validated_record = teacher.run_sandbox_validation(record.hypothesis_id)
    print(f"  -> Baseline Sharpe   : {validated_record.baseline_sharpe:.2f}")
    print(f"  -> Experiment Sharpe : {validated_record.experiment_sharpe:.2f}")
    print(f"  -> Risk Delta        : {validated_record.risk_delta_pct*100:.1f}%")
    print(f"  -> Validation Status : {validated_record.validation_status} [PASS]")

    print("\n[Step 7: APPROVAL GATE] Simulating Human Change-Control Approval...")
    approved = provenance.approve_experiment(record.hypothesis_id, approver_id="officer_admin_01")
    print(f"  -> Approved By: {approved.approved_by} at {approved.approval_timestamp_utc}")
    print(f"  -> Ready for staged canary deployment under change control CR-AUREX-0104.")
    print("================================================================================")


def main():
    parser = argparse.ArgumentParser(description="AUREX Master Platform CLI")
    parser.add_argument("command", choices=["status", "scan", "run-cycle", "teacher-cycle", "serve"],
                        help="Command to run")
    args = parser.parse_args()

    ctx = setup_system()

    if args.command == "status":
        cmd_status(ctx)
    elif args.command == "scan":
        cmd_scan(ctx)
    elif args.command == "run-cycle":
        cmd_run_cycle(ctx)
    elif args.command == "teacher-cycle":
        cmd_teacher_cycle(ctx)
    elif args.command == "serve":
        from aurex.dashboard.app import start_server
        start_server()


if __name__ == "__main__":
    main()
