# FinLedger-AI — Master College Demonstration & Examination Guide

**Project:** FinLedger-AI: An Auditable Financial Transaction System with AI-Assisted Fraud Detection  
**Audience:** Academic Evaluators, External Examiners & Capstone Review Committee  
**Execution Environment:** Windows 11 / Local PostgreSQL 16+ / FastAPI / React 19 + TypeScript  
**Status:** Fully Implemented & Empirically Verified  

---

## 1. System Architecture & High-Integrity Invariants

FinLedger-AI combines Database Systems (DBMS) rigor, double-entry financial accounting, and transparent AI detection:

```
[ Customer / Staff Browser ]
           │
           ▼
[ React 19 + TypeScript Frontend (Editorial Workbench) ]
           │  HTTPS / REST / Idempotency-Key: UUIDv4
           ▼
[ FastAPI Backend Application (Python 3.12, Pydantic v2) ]
     ├── PayeeGuard (Beneficiary Verification & Deviation Guard)
     ├── LedgerGraph (Point-In-Time Temporal Money-Flow Graph Engine)
     ├── Fraud Lab (Ephemeral In-Memory Multi-Model Benchmarking)
     └── AI Health Governance (Readiness Fingerprinting & Input Drift Monitoring)
           │  SQLAlchemy 2.0 / Alembic (Reversible Migrations)
           ▼
[ PostgreSQL 16 Relational Engine (Sole Source of Truth) ]
     ├── NUMERIC(15,2) Precision (INR Currency Strictly Enforced)
     ├── Double-Entry Balanced Posting Trigger: trg_verify_ledger_balance
     ├── Append-Only Immutability Triggers: trg_immutable_ledger_entries, trg_immutable_audit_logs
     ├── Deterministic Row-Level Locking: SELECT ... ORDER BY id FOR UPDATE
     └── Independent Audit Logging: Autonomous Failure Persistence
```

---

## 2. Pre-Demonstration Verification Check

Before presenting to evaluators, verify all services are active:

```powershell
# 1. Verify Backend Health
curl http://127.0.0.1:8000/health
# Expected: {"status":"healthy","service":"FinLedger-AI","environment":"development"}

# 2. Run Comprehensive Automated Test Suite (164 Backend + 23 Frontend)
cd backend
..\.venv\Scripts\pytest.exe -q
# Expected: 164 passed, 1 warning (third-party httpx deprecation notice)

cd ..\frontend
npm test
# Expected: 23 passed across 6 test files

# 3. Confirm the Random Forest model is loaded (not the rule fallback)
#    Staff -> Model health should show "Random Forest" and a SHA-256 fingerprint.
#    If it shows "Running on the rule baseline", run from backend/:
#    ..\.venv\Scripts\python.exe -m ml.train --count 10000   then restart the API.

# 4. Check Ledger Mathematical Reconciliation
cd ..\backend
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py
# Expected: Discrepancy Count: 0, Global Net Ledger Delta: INR 0.00, Status: BALANCED
```

---

## 3. Repeatable 16-Step Live Demonstration Protocol

### Step 1: Customer Registration & Primary Account Provisioning
- **Concept Demonstrated**: Deterministic onboarding with zero-balance liability account provisioning.
- **Action**:
  - In browser at `http://localhost:5173/register`, register customer:
    - Full Name: `Vikram Patel`, Username: `vikram_patel`, Email: `vikram@finledger.io`, Password: `Password123!`.
  - Log in at `/login`, then click **Open savings account** on the dashboard.
- **Expected Observation**:
  - Registration creates the customer profile only; the account is opened explicitly.
  - The new `SAVINGS` account (e.g. `INR-SAV-1A2B3C4D`) starts at exactly **₹0.00**. Demonstrates that money is never manufactured during account creation.
  - Tip: open a second account (or register a second customer) to have a transfer recipient for Step 3.

---

### Step 2: Simulated Opening Deposit via Clearing Account
- **Concept Demonstrated**: Strict Double-Entry Invariant ($\sum \text{Debits} == \sum \text{Credits}$).
- **Action**:
  - On Dashboard, click **"Deposit funds"**.
  - Amount: `100000`, Description: `Initial verified salary deposit`. Click **Add deposit**.
- **Expected Observation**:
  - Available balance updates atomically to **₹100,000.00**.
  - PostgreSQL trigger `trg_verify_ledger_balance` verifies balanced debit and credit legs at commit:
    - `CREDIT` ₹100,000.00 on customer liability account.
    - `DEBIT` ₹100,000.00 on system clearing account (`INR-SYS-CLEARING`).

---

### Step 3: PayeeGuard Beneficiary Verification Preview (Innovation B)
- **Concept Demonstrated**: Pre-transfer recipient verification preventing misdirected payments and impersonation scams (NPCI UPI Addendum 101/A & RBI FREE-AI aligned).
- **Action**:
  - Navigate to **Transfers** (`/transfers`) $\to$ Click **"New transfer"**.
  - **From**: the account holding ₹100,000.00.
  - **To account number**: the recipient's account number (e.g. `INR-SAV-1A2B3C4D`), or pick one of your own accounts from the shortcut chips. Customers never need internal UUIDs.
  - Amount: `25000`.
  - Click **"Review transfer"**.
- **Expected Observation**:
  - The modal invokes `POST /api/v1/transfers/preview` on the backend without moving any funds.
  - Displays authoritative **PayeeGuard Verification** card:
    - Legal Beneficiary Name (e.g. `Aarav Sharma` or verified account holder from database).
    - Masked Destination Account (e.g. `INR-••••C4D`).
    - Relationship: first-time recipient, or how many times you have paid this account before.
    - Funds are checked here too: an amount above the available balance is refused before anything is submitted.
    - Advisory Warnings if amount deviates significantly from counterparty baseline.

---

### Step 4: Transfer Execution & Digital Receipt Inspection
- **Concept Demonstrated**: Atomic transfer execution under canonical row locks with immediate receipt generation.
- **Action**:
  - In review modal, inspect the assigned `Idempotency key` (`UUIDv4`).
  - Click **"Send ₹25,000.00"**.
- **Expected Observation**:
  - Transfer posts atomically with status `POSTED`.
  - Balance decrements: ₹100,000.00 $\to$ **₹75,000.00**.
  - Displays the receipt (reference, status, posted time); the transfer appears at the top of the **Transfers** history.

---

### Step 5: Scoped Idempotency Replay (Zero Duplicate Debits)
- **Concept Demonstrated**: Non-repudiation and replay defense. Retrying identical requests returns cached results without duplicate money movements.
- **Action (API Simulation)**:
  - Resubmit the exact same transfer request with the identical `Idempotency-Key` header and payload.
- **Expected Observation**:
  - Server returns HTTP 200 OK (cached transaction record).
  - Balance remains strictly **₹75,000.00**; zero additional debits occur.

---

### Step 6: Overdraft Prevention & Autonomous Audit Persistence
- **Concept Demonstrated**: Check constraints (`cached_balance >= 0.00`) and independent audit persistence for failed transactions.
- **Action**:
  - In the UI, try to send `500000` (exceeding the available ₹75,000.00): PayeeGuard refuses it at the review step, before any request is submitted.
  - To show the server-side guarantee, submit the same over-limit transfer directly via Swagger (`POST /api/v1/transfers`, customer token, fresh `Idempotency-Key`).
- **Expected Observation**:
  - Rejection with HTTP 400 Bad Request: `Insufficient funds`.
  - Financial transaction is completely rolled back; balance remains **₹75,000.00**.
  - Independent audit transaction records failure event `TRANSFER_FAILED` in `audit_logs`, and the attempt appears in the customer's **Transfers** history as **Declined** with its reason.
  - Replaying the same `Idempotency-Key` returns the original failure, never a success.

---

### Step 7: Fraud Lab Seeded Benchmark (Innovation D)
- **Concept Demonstrated**: Reproducible, isolated multi-model benchmarking comparing Rule Baseline, Random Forest, LedgerGraph, and Hybrid Ensemble.
- **Action**:
  - Log in as compliance staff (`priya_investigator` / `Password123!`).
  - Navigate to **Fraud Lab Benchmark** (`/staff/fraud-lab`).
  - Select Scenario: `ALL_SCENARIOS_BENCHMARK`.
  - Seed: `42`, Sample Size: `200`. Click **Run Benchmark Simulation**.
- **Expected Observation**:
  - Prominent safety banner: `SYNTHETIC SIMULATION — NOT REAL CUSTOMER ACTIVITY. Zero financial records or balances created.`
  - Comparative Performance Table:
    - Rule Baseline: ~75% Precision, ~80% Recall.
    - Random Forest: ~85% Precision, ~75% Recall.
    - LedgerGraph: Detects 100% of Fan-In and Circular Wash scenarios.
    - Hybrid Ensemble: Achieves top F1 score by combining tabular features with graph heuristics.
  - Confusion matrices and scenario breakdown by pattern family.

---

### Step 8: LedgerGraph Temporal Money-Flow Explorer (Innovation A)
- **Concept Demonstrated**: Point-in-time relational graph analysis over accounts (nodes) and transfers (directed edges).
- **Action**:
  - Navigate to **LedgerGraph Explorer** (`/staff/graph`).
  - Set Time Window: `72 Hours`, Hop Depth: `2 Hops`.
- **Expected Observation**:
  - Interactive SVG visual graph displays money movements between accounts.
  - Hovering/clicking nodes displays account holder, type, and balance.
  - Clicking edges displays transfer reference, amount, and timestamp.
  - Pattern Findings stream highlights detected patterns:
    - `FAN_IN`: Multiple sources funnelling into a mule account.
    - `RAPID_PASS_THROUGH`: Fast crediting and onward forwarding within 4 hours.
    - `CIRCULAR_WASH`: Closed-loop transaction cycles.
  - Accessible Table View toggle provides full WCAG 2.2 AA compliant tabular inspection.

---

### Step 9: Multi-Detector Comparison on Graph Patterns
- **Concept Demonstrated**: Graph analysis catches multi-account flow patterns that tabular models miss.
- **Explanation**:
  - Standard Random Forest evaluates individual transaction rows independently (amount, velocity, z-score). It fails to see multi-hop layering across distinct accounts.
  - LedgerGraph reconstructs the directed money-flow graph at prediction time $t$ (strictly without future edge leakage), identifying circular wash cycles and fan-in funnels.

---

### Step 10: Unified Forensic Investigation Dossier (Innovation C)
- **Concept Demonstrated**: Traceable evidence connecting every alert to source ledger legs and human decisions.
- **Action**:
  - Navigate to **Fraud alerts** (`/staff/fraud`).
  - Click **"Open dossier"** on any alert.
- **Expected Observation**:
  - Dossier drawer opens with complete evidentiary layers:
    1. **Statistical Rationale & Model Version**: Risk score, decision, and feature snapshot.
    2. **Authoritative Double-Entry Ledger Legs**: PostgreSQL source of truth displaying balanced `DEBIT` and `CREDIT` legs with account numbers.
    3. **LedgerGraph Findings**: Associated network patterns and severity scores.
    4. **Chronological Evidentiary Timeline**: Each entry is labelled by source: ledger fact, rule, model, LedgerGraph, or staff action.
    5. **Forensic Notes**: Append-only investigator commentary.

---

### Step 11: Authorized Staff Determination with Mandatory Notes
- **Concept Demonstrated**: Human-in-the-loop review governance; AI is advisory only.
- **Action**:
  - In Forensic Dossier, choose **Confirm fraud**.
  - Enter a Reason (required): `Identified coordinated pass-through pattern matching mule account typology. Confirmed for escalation.`
  - Click **Commit Determination**.
- **Expected Observation**:
  - Review status updates to `CONFIRMED_FRAUD`.
  - Staff user ID and timestamp recorded.
  - Immutable audit trail records `FRAUD_ALERT_REVIEW` event.

---

### Step 12: Customer Recourse & Dispute Tracking (Innovation C)
- **Concept Demonstrated**: Customer right to contest transactions without arbitrary balance mutations.
- **Action**:
  - Switch to Customer Portal (`/transfers`).
  - In the history, click **Dispute** on a posted transfer.
  - Problem: *I didn't make this transfer*, Description: `Transaction executed from unrecognized IP while traveling.` Click **Open dispute**.
  - Navigate to **Disputes** (`/disputes`).
- **Expected Observation**:
  - Dispute case opened with status `OPEN`.
  - Chronological append-only case event logged (`DISPUTE_OPENED`).
  - Customer can submit supplementary clarifications (`CUSTOMER_RESPONSE`).
  - Balance is strictly preserved; dispute filing never reverses funds autonomously.

---

### Step 13: Staff Dispute Investigation & Resolution
- **Concept Demonstrated**: Controlled case lifecycle (`OPEN` $\to$ `INVESTIGATING` $\to$ `RESOLVED`).
- **Action (Staff)**:
  - As staff, open **Disputes** (`/staff/disputes`), select the case, choose **Start investigating** with a note, then **Resolve in the customer’s favour** with a note.
- **Expected Observation**:
  - Immutable `case_events` record each state transition with actor role and timestamp.
  - Resolving records the decision only; no money moves.
- **Action (Admin correction)**:
  - Sign in as `admin_system`, open the same case in **Disputes**, enter a reason under **Correct the ledger**, click **Reverse transfer**, then **Confirm reversal**.
- **Expected Observation**:
  - A new balanced `CORRECTION_REVERSAL` posting moves the amount back; the original ledger legs are untouched and the original transfer shows **Reversed** in the customer's history.
  - `TRANSFER_REVERSED` is written to the audit trail in the same database transaction. A second attempt is refused (HTTP 409), staff users get HTTP 403, and Reconciliation still reports zero discrepancies.

---

### Step 14: AI Runtime Health & Governance Dashboard (Innovation E)
- **Concept Demonstrated**: Production AI transparency, artifact fingerprinting, and feature drift monitoring.
- **Action**:
  - Navigate to **Model health** (`/staff/ai-health`).
- **Expected Observation**:
  - Model Runtime State: Active model version (`rf-v1.0.0`) and SHA-256 artifact fingerprint.
  - Fallback Mode Disclosure: Transparently discloses if deterministic rules are operating in failsafe mode.
  - Model inputs: lists the 12 tabular features the Random Forest uses.
  - Input drift: distribution status and the mean amount of recent scored transfers, compared with the synthetic training baseline. (A full per-feature PSI is not computed.)
  - Documented Academic Limitations: Discloses that models are advisory and synthetic evaluations do not equate to real-world efficacy.

---

### Step 15: Database Trigger Defense (Attempted Admin Tampering)
- **Concept Demonstrated**: PostgreSQL triggers defend financial data against direct SQL manipulation.
- **Action (Terminal Command)**:
  ```powershell
  cd backend
  ..\.venv\Scripts\python.exe -c "
  from app.core.config import settings
  from sqlalchemy import create_engine, text
  engine = create_engine(settings.sync_database_url)
  with engine.connect() as conn:
      try:
          conn.execute(text('UPDATE ledger_entries SET amount = 9999.00 WHERE sequence_num = 1;'))
          conn.commit()
          print('VULNERABILITY: Ledger entry was updated!')
      except Exception as err:
          print('PROTECTED BY POSTGRESQL TRIGGER:', err)
  "
  ```
- **Expected Observation**:
  - PostgreSQL trigger `trg_immutable_ledger_entries` raises exception:
    `Modification of committed ledger entries is strictly prohibited.`

---

### Step 16: DBMS Performance & Query Plan Optimization
- **Concept Demonstrated**: Relational database query tuning using `EXPLAIN (ANALYZE, BUFFERS)`.
- **Action (Terminal Command)**:
  ```powershell
  cd backend
  ..\.venv\Scripts\python.exe scripts/benchmark_dbms.py --db-name finledger_bench --run
  ```
- **Expected Observation**:
  - **Workload 2B (Staff Transfer Search)**: Composite index `idx_transfers_status_created` executes in **~0.10 ms** (106 buffers) vs. Sequential Scan **10.92 ms** (2,208 buffers) — **105x speedup**.
  - **Workload 1 (Ledger History)**: Composite index `idx_ledger_entries_account_created_seq` serves queries in **~0.08 ms** without memory sort overhead.
  - **Trade-Off Analysis**: Explains write overhead of multi-column indexes during high-concurrency ingestion.

---

## 4. Summary Acceptance Matrix

| Innovation / Requirement | Primary Mechanism | Verification Method | Result |
| :--- | :--- | :--- | :--- |
| **Double-Entry Correctness** | PostgreSQL Constraint Trigger | `pytest test_ledger_trigger.py` | **PASS** (100% Balanced) |
| **Deterministic Concurrency** | Canonical Row Locks (`ORDER BY id FOR UPDATE`) | `pytest test_concurrency.py` | **PASS** (Zero Deadlocks/Overdrafts) |
| **Ledger Immutability** | `BEFORE UPDATE OR DELETE` Triggers | `pytest test_immutability_triggers.py` | **PASS** (Protected) |
| **Innovation A: LedgerGraph** | Temporal Relational Network Analysis | `pytest test_innovations_graph.py` | **PASS** (Fan-In/Circular Caught) |
| **Innovation B: PayeeGuard** | Pre-Transfer Recipient Preview & Warnings | `pytest test_innovations_payee_guard.py` | **PASS** (Beneficiary Verified) |
| **Innovation C: Evidence Dossier** | Multi-Layer Evidentiary Timeline | `pytest test_innovations_fraud_lab_and_health.py` | **PASS** (Source-Linked) |
| **Innovation C: Recourse Workflow** | Append-Only Case Event Lifecycle | `pytest test_innovations_disputes.py` | **PASS** (Audited Recourse) |
| **Innovation D: Fraud Lab** | Ephemeral Multi-Model Benchmarking | `pytest test_innovations_fraud_lab_and_health.py` | **PASS** (Ledger Isolated) |
| **Innovation E: AI Health** | Runtime Fingerprinting & Input Drift | `pytest test_innovations_fraud_lab_and_health.py` | **PASS** (Transparent Disclosure) |
| **Editorial Frontend** | React 19 + TypeScript + Tabular Numerals | `npm run test` + `npm run build` | **PASS** (16/16 Tests, Clean Build) |
