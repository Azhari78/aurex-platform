# AUREX MASTER PLATFORM v1.3.1 (AI Brain + Teacher)

Sistem platform dagangan algoritma pelbagai pasaran (*institutional-grade multi-market algorithmic trading platform*) berasaskan spesifikasi rasmi **AUREX MASTER BLUEPRINT v1.3.1 AI BRAIN + TEACHER (Audited / Design Freeze)**.

---

## 🏛️ Seni Bina Teras & Hierarki Autoriti

```text
User / Voice / Dashboard
           │
           ▼
     AIA AI Brain ───────────────► External Intelligence Gateway (EIG)
           │                        (Strict Trust, Sanitization & Deny-by-Default)
           ├────────────────────────┬────────────────────────┐
           ▼                        ▼                        ▼
     FX MHE Engine        Crypto Trading Engine     Multi-chain DeFi Engine
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    ▼
                         Economics Authority
                   (Net EV >= 0.5% & R:R Verification)
                                    │
                                    ▼
                         Risk & Capital Authority
                   (Portfolio Caps, Drawdown Circuit Breaker)
                                    │
                                    ▼
                          Global Governor
                 (Sole Atomic Authorization Authority,
                  Kill-Switch & Paper Safety Gates)
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
             Global Ledger                  Execution Engine
       (Double-Entry Multi-Currency      (Paper Broker Simulation &
      & Capital Reservations with Hash)   Authoritative Reconciliation)
```

---

## 🚀 Status Pelaksanaan Terbuka (Open Items Resolved)

| Kod | Komponen / Keperluan | Status | Modul Pelaksanaan |
| :--- | :--- | :---: | :--- |
| **P0-01** | Global Core ledger, capital reservation & Governor atomic consumption | ✅ **IMPLEMENTED** | `aurex.core.ledger`, `aurex.core.governor` |
| **P0-02** | Identity, entitlements, MFA & HMAC confirmation anti-replay | ✅ **IMPLEMENTED** | `aurex.core.identity` |
| **P0-03** | Core-FX explicit PAPER adapter & broker-truth reconciliation | ✅ **IMPLEMENTED** | `aurex.engines.fx`, `aurex.execution.reconciliation` |
| **P0-04** | AIA AI Brain runtime + EIG allowlisted trust connectors | ✅ **IMPLEMENTED** | `aurex.ai_brain.brain`, `aurex.ai_brain.eig` |
| **P0-05** | Crypto Trading Engine (liquid scanner, spread/microstructure, fee-aware) | ✅ **IMPLEMENTED** | `aurex.engines.crypto` |
| **P0-06** | Multi-chain DeFi Engine (Lending APR, UniV3 routing, gas estimation) | ✅ **IMPLEMENTED** | `aurex.engines.defi` |
| **P0-07** | AIA Teacher experiment, provenance lineage & sandbox approval pipeline | ✅ **IMPLEMENTED** | `aurex.teacher.supervisor`, `aurex.teacher.provenance` |
| **P0-08** | Complete Core contracts, exact Decimal budgets, and typed Pydantic models | ✅ **IMPLEMENTED** | `aurex.core.models` |
| **P0-09** | Unified acceptance test suite covering 3 engines + AIA Brain + Teacher | ✅ **IMPLEMENTED** | `tests/` (21 unit & integration tests) |
| **P0-10** | Economic calibration (Net EV), failure injection, and risk gates | ✅ **IMPLEMENTED** | `aurex.economics.evaluator`, `aurex.risk.manager` |
| **P1-01** | Modern interactive unified dashboard & CLI runtime | ✅ **IMPLEMENTED** | `aurex.dashboard`, `aurex.cli` |

---

## 🔒 Prinsip Keselamatan & Invarian (Security Invariants)

1. **Deny by Default:** Tiada sebarang pesanan atau transaksi boleh dihantar secara terus oleh AI Brain atau Engine tanpa kelulusan sah daripada Global Governor.
2. **Atomic One-Time Authorization:** Token autorisasi (`auth_token`) dijana oleh Governor hanya boleh digunakan sekali sahaja. Sebarang cubaan replay akan disekat serta-merta.
3. **LIVE Mode LOCKED:** Mod dagangan sebenar (LIVE) dikunci secara kekal dalam fasa ini (`LIVE_LOCKED = True`), hanya mod simulasi PAPER yang dibenarkan.
4. **Independent Economics & Risk Authority:** AIA Brain tidak boleh mengatasi (*override*) keputusan Economics (EV negatif) atau Risk (had portfolio).
5. **AIA Teacher Is Not An Executor:** Teacher hanya bertindak sebagai penyelidik makmal kawalan (`Observe -> Diagnose -> Hypothesis -> Sandbox -> Validation -> Human Approval`) dan tidak mempunyai akses dagangan langsung.

---

## 💻 Panduan Penggunaan CLI

Buka PowerShell di direktori projek:
```powershell
cd C:\Users\azhar\.gemini\antigravity\scratch\aurex-master-platform
$env:PYTHONPATH="src"
```

### 1. Semak Status Platform & Ledger
```powershell
python -m aurex.cli status
```

### 2. Imbas Pasaran (FX, Crypto, DeFi) & Jana Cadangan AIA Brain
```powershell
python -m aurex.cli scan
```

### 3. Jalankan Kitaran Lengkap Autonomi (Scan -> Authorize -> Execute -> Reconcile)
```powershell
python -m aurex.cli run-cycle
```

### 4. Jalankan Kitaran Pembelajaran AIA Teacher & Provenance
```powershell
python -m aurex.cli teacher-cycle
```

### 5. Jalankan Web Dashboard Interaktif
```powershell
python -m aurex.cli serve
```
Buka pelayar web di: **http://127.0.0.1:8000**

---

## 🧪 Menjalankan Ujian Unit & Integrasi
```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```
Semua 21 ujian merangkumi:
- `test_ledger.py`: Multi-currency deposits, capital reservations, double-entry audit chain.
- `test_governor.py`: Atomic single-use token consumption, replay denial, kill switch, high-risk approval.
- `test_identity.py`: HMAC-SHA256 signature verification, anti-replay nonce, revocation.
- `test_eig.py`: Allowlisted connectors, prompt injection quarantine, trust scoring.
- `test_economics_and_risk.py`: Net EV thresholds, risk-to-reward ratio, portfolio caps.
- `test_teacher.py`: Observation, diagnosis, hypothesis provenance hashing, approval gates.
- `test_integration_cycle.py`: Kitaran hujung-ke-hujung (*end-to-end*).
