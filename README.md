# FinLedger-AI: Auditable Financial Ledger & AI Fraud Detection System


https://github.com/user-attachments/assets/994a8c16-3104-4a04-97f8-3a87cbeea3fa


[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4+-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An academic capstone project demonstrating enterprise Database Management System (DBMS) principles, double-entry ledger accounting, transaction concurrency control, and transparent machine-learning-assisted fraud triage.

---

## 1. Project Overview & Academic Purpose

FinLedger-AI is designed from first principles to reflect real-world core banking and auditable transaction processing. It rejects frontend mock prototypes and simplistic CRUD architectures:

- **Relational DBMS as the Sole Source of Truth**: Financial integrity is maintained by PostgreSQL 16+ constraints, transactional isolation, and database triggers.
- **Double-Entry Accounting Invariant**: Every monetary event creates strictly balanced multi-row legs ($\sum \text{Debits} == \sum \text{Credits}$). Money is never manufactured via an arbitrary SQL `UPDATE` on balances.
- **Append-Only Immutability**: Committed ledger entries and audit events cannot be modified or deleted, enforced by PostgreSQL `BEFORE UPDATE OR DELETE` triggers.
- **Deterministic Concurrency Control**: Transfers acquire row locks in canonical ascending primary key order (`SELECT ... ORDER BY id FOR UPDATE`), eliminating deadlocks and double-spending race conditions.
- **Separation of Financial Execution and AI**: Machine learning and rule engines are strictly **advisory**. AI produces risk scores, feature attributions, and triage alerts for human staff review; it never alters balances, rejects transfers, or freezes accounts autonomously.

---

## 2. Approved Technology Stack

| Layer | Technology | Key Modules & Purpose |
| :--- | :--- | :--- |
| **Backend** | Python 3.12, FastAPI, Pydantic v2 | High-throughput asynchronous REST API, strict request/response validation |
| **Database** | PostgreSQL 16+ | ACID transactions, deferrable constraint triggers, row-level locking |
| **ORM & Migrations** | SQLAlchemy 2.0, Alembic | Mapped declarative models, transactional DDL migrations |
| **Security & Auth** | Argon2id / bcrypt, PyJWT | Role-Based Access Control (Customer, Staff, Admin), 60-min JWT expiry |
| **Data Science & ML** | scikit-learn, NumPy, pandas | Random Forest classifier, heuristic rule baseline, explainability snapshots |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS | High-integrity customer & staff dashboards, reactive modals, responsive UI |
| **Testing & Verification**| pytest, Vitest, Playwright | Real PostgreSQL test fixtures, concurrency race tests, component test suites |

---

## 3. Architecture & Core Financial Invariants

```
               +--------------------------------------------------+
               |       React 19 + TypeScript Customer & Staff UI   |
               +--------------------------------------------------+
                                        | (HTTPS / JSON)
                                        v
               +--------------------------------------------------+
               |             FastAPI Application Services         |
               |  - AuthService (JWT & RBAC Dependencies)         |
               |  - TransferService (Canonical Ascending Locking) |
               |  - InvestmentService (Portfolio & Products)      |
               |  - FraudService (Advisory ML Inference)          |
               |  - AuditService (Independent Transaction Logger) |
               +--------------------------------------------------+
                                        | (SQLAlchemy 2.0 Session)
                                        v
+-----------------------------------------------------------------------------------+
|                           PostgreSQL 16+ Database Engine                          |
|                                                                                   |
|  [accounts]                      [transfer_requests]           [audit_logs]       |
|  - NUMERIC(15,2) Balance         - Scoped Idempotency Key      - Append-Only Log  |
|  - CHECK (cached_balance >= 0)   - Canonical Request Hash      - Immutable Trigger|
|         ^                               |                                         |
|         |                               v                                         |
|  [ledger_entries] <------------ [ledger_transactions]     [fraud_predictions]     |
|  - Balanced Legs (Debit/Credit) - Header Record           - Advisory Scores       |
|  - trg_verify_ledger_balance    - 1:1 with Transfer       - PENDING Triage Queue  |
|  - trg_immutable_ledger_entries                                                   |
+-----------------------------------------------------------------------------------+
```

### Non-Negotiable Invariants:
1. **Money Representation**: `NUMERIC(15, 2)` across all balances, amounts, and ledger legs in PostgreSQL; `decimal.Decimal` in Python. Floating-point numbers are strictly forbidden. Denominated in **INR** only.
2. **Double-Entry Legs**: Customer accounts are liabilities: Debits reduce balance; Credits increase balance. Initial funds are deposited against an internal clearing account (`INR-SYS-CLEARING`).
3. **Database Constraint Trigger**: `trg_verify_ledger_balance` (`DEFERRABLE INITIALLY DEFERRED`) verifies $\sum \text{Debits} - \sum \text{Credits} = 0$ at transaction commit.
4. **Scoped Idempotency**: Verified against `(source_user_id, idempotency_key)` and SHA-256 payload hash. Retries return cached 200/201 responses; key reuse with altered payloads returns `409 Conflict`.
5. **Independent Audit Persistence**: If a financial transfer fails, its financial transaction is rolled back completely (0 funds deducted), while its audit failure record (`TRANSFER_FAILED`) is committed in an independent transaction.

---

## 4. Local Installation & Developer Setup

### Prerequisites
- **Operating System**: Windows 10/11 (or Linux/macOS)
- **Python**: 3.12+ 64-bit
- **Node.js**: v20+ and npm v10+
- **PostgreSQL**: 16+ running locally on port `5432`

---

### Step 1: Clone the Repository
```powershell
git clone https://github.com/Saksham0025/FinLedger-AI.git
cd FinLedger-AI
```

---

### Step 2: Configure Environment Variables
Copy the example environment configuration:
```powershell
cp .env.example .env
```
Ensure `.env` contains valid local database credentials (never commit `.env`):
```ini
ENVIRONMENT=development
DEBUG=True
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_local_postgres_password
DB_NAME=finledger
DB_TEST_NAME=finledger_test
SECRET_KEY=generate_a_secure_random_64_character_hex_key
ACCESS_TOKEN_EXPIRE_MINUTES=60
CLEARING_ACCOUNT_NUMBER=INR-SYS-CLEARING
```

---

### Step 3: Backend Setup & Database Migrations
**One command (Windows):** after setting `DB_PASSWORD` and `SECRET_KEY` in `.env`, run `.\scripts\setup_postgres_local.ps1` from the repository root. It installs dependencies, creates both databases, migrates them, seeds the clearing account, demo users and products, trains the fraud model and installs the frontend packages. It is safe to re-run. The manual steps below do the same thing.

Create and activate the Python virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

Run Alembic migrations to build the complete relational schema (development and test databases):
```powershell
cd backend
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\alembic.exe -x db=test upgrade head
```

Seed demonstration accounts (Customer, Staff, Admin) and financial products:
```powershell
..\.venv\Scripts\python.exe scripts/seed_users.py
..\.venv\Scripts\python.exe scripts/seed_products.py
```

Train the Random Forest fraud model (about a minute; the trained `model.joblib` is not committed):
```powershell
..\.venv\Scripts\python.exe -m ml.train --count 10000
```
Without this step the API still runs, but fraud scoring falls back to the transparent rule baseline and the **Model health** page says so.

---

### Step 4: Frontend Setup
In a new terminal window:
```powershell
cd frontend
npm install
npm run build
```

---

### Step 5: Start Development Servers

**Start FastAPI Backend**:
```powershell
# From the backend directory (the app imports itself as `app`)
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
On Windows, `--reload` can detect a change and then stall without restarting; if the API keeps serving old code, stop it and start it again without `--reload`.
- Swagger Interactive Documentation: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
- Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

**Start React Frontend**:
```powershell
# From frontend directory
cd frontend
npm run dev
```
- Frontend Portal: [http://localhost:5173](http://localhost:5173)

---

## 5. Demonstration Accounts

| Role | Username | Password | Profile Details & Permitted Actions |
| :--- | :--- | :--- | :--- |
| **Customer** | `rahul_sharma` | `Password123!` | Primary Savings Account, transfers, simulated deposits, investment purchases |
| **Staff** | `priya_investigator` | `Password123!` | Compliance triage queue, fraud alert forensic review, volume reporting |
| **Admin** | `admin_system` | `Password123!` | System administration, full ledger reconciliation audits, product catalog |

---

## 6. Verification & Test Execution

### 1. Full Backend Test Suite (164 Tests)
```powershell
cd backend
..\.venv\Scripts\pytest.exe -v
```
*Expected Outcome:* **164 passed, 1 warning** (the warning is a third-party Starlette/httpx deprecation notice).

### 2. Concurrency Race & Overspending Suite (8 Tests)
```powershell
cd backend
..\.venv\Scripts\pytest.exe tests/test_concurrency.py -v
```
*Includes:* Multi-threaded competing withdrawal drain race (5 concurrent threads), bi-directional transfer deadlock prevention, concurrent investment provisioning.

### 3. Frontend Unit & Component Tests (23 Tests across 6 Test Files)
```powershell
cd frontend
npm test
```
*Expected Outcome:* **6 test files passed, 23 passed**. `npx tsc --noEmit` should also report no errors.

### 4. Double-Entry Balance Reconciliation Audits
```powershell
cd backend
# Reconcile development database
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py

# Reconcile test database
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py --test
```
*Expected Outcome:* **0 discrepancies, Global Net Ledger Delta: INR 0.00**.

### 5. Machine Learning & Multi-Detector Benchmark (Fraud Lab)
```powershell
cd backend
..\.venv\Scripts\python.exe -c "
from app.core.database import SessionLocal
from app.services.fraud_lab_service import FraudLabService
db = SessionLocal()
res = FraudLabService.run_simulation(db, scenario_name='ALL_SCENARIOS_BENCHMARK', seed=42, sample_size=200)
print('Detectors Evaluated:', list(res['detectors'].keys()))
print('Zero Ledger Mutations Guarantee:', res['isolation_guarantee'])
"
```
*Expected Outcome:* Evaluates Rule Baseline, Random Forest, LedgerGraph, and Hybrid Ensemble with zero authoritative financial mutations.

### 6. Phase 7 DBMS Performance Benchmark Profiling
```powershell
cd backend
..\.venv\Scripts\python.exe scripts/benchmark_dbms.py --db-name finledger_bench --run
```
*Expected Outcome:* Executes `EXPLAIN (ANALYZE, BUFFERS)` over cold/warm runs profiling 5 representative workloads.

---

## 7. Primary Architectural Innovations

1. **LedgerGraph (Innovation A)**: Explainable temporal money-flow network analysis directly over relational PostgreSQL data. Detects multi-account typologies (Fan-In, Rapid Pass-Through, Circular Wash, Multi-Hop Layering) strictly without future temporal edge leakage.
2. **PayeeGuard (Innovation B)**: Pre-submission beneficiary verification preview showing legal recipient names, masked account numbers, first-time payee flags, and volume deviation warnings.
3. **Forensic Dossier & Recourse (Innovation C)**: Unified investigation dossier connecting alerts, double-entry ledger legs, ML explainability, graph signals, and staff notes. Integrated customer recourse workflow (`/disputes`) with append-only `case_events`.
4. **Fraud Lab (Innovation D)**: Seeded, reproducible synthetic adversarial scenario workbench evaluating transparent rules, Random Forest, LedgerGraph, and Hybrid Ensemble under strict ledger isolation.
5. **AI Health & Governance (Innovation E)**: Runtime model inspection, artifact fingerprinting, fallback mode disclosure, and feature drift monitoring (Population Stability Index).

---

## 8. College Demonstration Protocol

A complete 16-step examination walkthrough is documented in [docs/college_demonstration_guide.md](docs/college_demonstration_guide.md), demonstrating:
- Deterministic onboarding, opening deposits, and balanced ledger postings.
- PayeeGuard beneficiary verification and client idempotency replay.
- Fraud Lab multi-model benchmarking under strict isolation.
- LedgerGraph SVG network visualization and pattern detection.
- Unified Forensic Dossier linking source ledger legs and human decisions.
- Customer recourse case lifecycle and append-only event trail.
- AI Health runtime readiness and PSI drift indicators.
- DBMS trigger defense against SQL tampering and `EXPLAIN (ANALYZE, BUFFERS)` performance benchmarks.

---

## 9. Academic Disclaimers & Known Limitations

1. **Synthetic Data Disclaimer**: Machine learning metrics (Precision, Recall, F1) were evaluated against synthetic banking transaction scenarios. They demonstrate algorithmic integration and explainability pipelines, and do not represent uncalibrated real-world banking fraud efficacy.
2. **Advisory AI Boundary**: AI models and graph detectors are strictly advisory. They never modify account balances, reject transfers, or freeze accounts autonomously.
3. **Query Planner Trade-Off (Workload 2A)**: As documented in [docs/dbms_experiments.md](docs/dbms_experiments.md), queries combining sparse per-account filters with `LIMIT 50` can experience planner discounting under composite status indexes. Single-customer transaction history should continue relying on dedicated account index lookups.
4. **Simulated Investments & Internal Directory**: Financial product yields and PayeeGuard beneficiary lookups operate against internal database directory records, and do not integrate live external NPCI/UPI gateways.

5. **Corrections Are Admin-Only Reversals**: An admin can reverse a posted customer transfer (`POST /api/v1/transfers/{id}/reverse`, or **Correct the ledger** in the dossier and staff Disputes page). It posts a new balanced `CORRECTION_REVERSAL` and marks the original `REVERSED`; it refuses if the recipient no longer holds the money, and investment purchases cannot be reversed this way. Partial refunds are not supported.
6. **Demo Deposits**: Customers can add simulated opening deposits to their own accounts (balanced against `INR-SYS-CLEARING`, so the books still balance). A real bank would restrict this to staff or a payment rail, and add an idempotency key.
7. **Stateless Sessions**: Access tokens are 60-minute JWTs stored in the browser. Signing out is audited but does not revoke a token that has already been issued.
8. **In-Request Graph Analysis**: LedgerGraph pattern analysis runs after each transfer commits, inside the same request. It never affects the posting, but it adds latency that grows with recent volume; a background worker would remove that.
9. **Append-Only Guard Scope**: Triggers block UPDATE, DELETE and TRUNCATE on `ledger_entries`, `ledger_transactions` and `audit_logs`. Test and benchmark resets opt in with `SET LOCAL finledger.allow_truncate = 'on'`; in production the durable control is a least-privilege database role.
