# AGENTS.md — Persistent Operational Rules & Engineering Standards

**Project:** FinLedger-AI: An Auditable Financial Transaction System with AI-Assisted Fraud Detection  
**Audience:** AI Coding Assistants & Engineering Contributors  
**Status:** Mandatory & Persistent  

---

## 1. Project Identity & Purpose

FinLedger-AI is a high-integrity, auditable financial transaction system built as an academic capstone project demonstrating real Database Management Systems (DBMS) principles, double-entry ledger accounting, concurrency control, and transparent machine learning fraud detection.

**Fundamental Mandate**: Do not treat this as a simple CRUD app or a frontend mock prototype. The relational database is the sole source of truth. All financial actions must be backed by real PostgreSQL transactions, constraints, triggers, and automated test verifications.

---

## 2. Approved Technology Stack

All development must strictly adhere to the approved technology stack unless a documented incompatibility arises:

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS.
- **Backend**: Python 3.12, FastAPI, Pydantic v2.
- **Database**: PostgreSQL 16+.
- **ORM & Migrations**: SQLAlchemy 2.0 (mapped declarative models), Alembic.
- **Security & Auth**: Passlib (Argon2id / bcrypt), PyJWT, Pydantic-Settings.
- **Data Science & ML**: scikit-learn, pandas, NumPy.
- **Testing**: pytest (with real PostgreSQL test database fixtures).
- **Environment**: Native Windows PowerShell setup scripts with local PostgreSQL 16+ as the primary developer setup; Docker Compose supported as an optional alternative.
- **Version Control**: Git.

---

## 3. Mandatory Database & Financial Invariants

Every agent working on this repository must enforce these non-negotiable financial invariants:

1. **Money Representation**:
   - PostgreSQL: `NUMERIC(15, 2)` across all balances, amounts, and ledger legs.
   - Python: `decimal.Decimal` with explicit rounding. Floating-point types (`float`, `real`, `double`) are strictly prohibited for financial balances.
   - Currency: Denominated in **INR** only.
2. **Double-Entry Accounting Convention**:
   - Customer accounts are liabilities: Debits reduce balance; Credits increase balance.
   - Every financial transaction must create balanced debit and credit entries ($\sum \text{Debits} == \sum \text{Credits}$).
   - Opening funds must be deposited against an internal clearing account (`INR-SYS-CLEARING`). Money must never be manufactured by an arbitrary SQL `UPDATE` on balances.
3. **Multi-Row Balanced Postings Validation**:
   - Enforced at the database level via a PostgreSQL `CONSTRAINT TRIGGER` (`DEFERRABLE INITIALLY DEFERRED`) on `ledger_entries` that asserts $\sum \text{Debits} - \sum \text{Credits} = 0$ at transaction commit.
4. **Ledger & Audit Immutability**:
   - Committed `ledger_entries` and `audit_logs` are strictly append-only.
   - Prohibited: Application update/delete endpoints.
   - Enforced by PostgreSQL `BEFORE UPDATE OR DELETE` triggers that raise exceptions on any modification attempt.
   - Corrections must be recorded via new `CORRECTION_REVERSAL` double-entry transactions.
5. **Deterministic Concurrency Control**:
   - When transferring between accounts, row locks must be acquired in canonical ascending primary key order:
     `SELECT ... WHERE id IN (min_id, max_id) ORDER BY id FOR UPDATE;`
   - Deadlocks and double-spending race conditions are strictly eliminated by this protocol.
6. **Scoped Idempotency**:
   - Client sends an `Idempotency-Key` header (`UUIDv4`).
   - Scoped per authenticated customer `(source_user_id, idempotency_key)`.
   - Verified against a SHA-256 hash of the canonical request payload.
   - Identical re-submissions return cached 200/201 responses; key reuse with altered payloads returns `409 Conflict`.
7. **Atomic Balance Caching & Reconciliation**:
   - `accounts.cached_balance` must be updated within the same transaction as `ledger_entries`.
   - An automated reconciliation engine must continuously verify that `cached_balance == sum(credits) - sum(debits)` for all accounts.
8. **Separation of Financial Execution and AI**:
   - The ML subsystem and rule engine are strictly **advisory**.
   - AI outputs risk scores, explanations, and alerts for staff triage; it must **never** modify balances, reject transfers, or freeze accounts autonomously.
   - Alert review statuses are strictly governed by the canonical enum: `PENDING`, `CLEARED`, `CONFIRMED_FRAUD`, `ESCALATED`.
9. **Independent Audit Persistence for Failed Transactions**:
   - When a transfer fails (e.g., insufficient funds, invalid account, rejected state), the financial transaction (`financial_txn`) must be completely rolled back so zero account balances or ledger legs change.
   - The failure event (`transfer_requests` with `status = 'FAILED'`) and audit log (`audit_logs` with `action = 'TRANSFER_FAILED'`) must be persisted and committed in an **independent transaction (`audit_txn`)**.
   - Financial rollback must **never** erase or discard required audit evidence or failure records.

---

## 4. Security & Access Control Standards

1. **Credential Safety**:
   - Passwords must be hashed using Argon2id or bcrypt (cost factor 12).
   - Plaintext passwords, secrets, or JWT tokens must never be written to logs, database audit fields, or source control.
2. **Authentication & Authorization**:
   - JWT tokens must have an expiration window (60 minutes).
   - Server-side RBAC dependencies must guard every API route (`require_customer`, `require_staff`, `require_admin`).
   - Customer endpoints must strictly verify account ownership (`account.customer.user_id == current_user.id`). Never rely on client-supplied identifiers.
3. **API Boundary Validation**:
   - All input data must be strictly validated by Pydantic schemas.
   - Database errors or internal exceptions must never leak raw stack traces to client responses.

---

## 5. Testing & Verification Requirements

1. **Real PostgreSQL Fixtures**:
   - Concurrency tests, transaction isolation tests, deferrable triggers, and lock contention suites must run against a real PostgreSQL test database. Never substitute SQLite for PostgreSQL concurrency verification.
2. **Mandatory Test Suites**:
   - Unit and integration tests for auth, transfers, insufficient funds, same-account transfers, and forced rollback.
   - Concurrency race-condition tests (concurrent withdrawals draining funds to zero; concurrent bi-directional transfers).
   - Idempotency replay and payload conflict tests.
   - Trigger-enforced ledger and audit immutability tests.
   - Full system balance reconciliation test.
   - Audit trail persistence test verifying failed transfers preserve audit records despite financial rollback.
3. **Honest Reporting Rule**:
   - Never remove or weaken a test simply to make a suite pass.
   - Never claim execution or verification that did not take place.
   - Report actual terminal command outputs, exit codes, and test results truthfully.
   - All performance figures mentioned during planning are illustrative targets only; never report benchmark numbers without verified empirical `EXPLAIN (ANALYZE, BUFFERS)` execution.

---

## 6. Incremental Phased Workflow

All development must proceed through the seven approved phases documented in `docs/phase_roadmap.md`:
1. **Phase 1**: Database Foundation, Migrations & Schema Constraints
2. **Phase 2**: Authentication, Authorization & Security Architecture
3. **Phase 3**: Core Double-Entry Ledger & Concurrency Engine
4. **Phase 4**: Synthetic Data Generator & AI Fraud Detection Pipeline
5. **Phase 5**: Financial Products, Investments & Reporting
6. **Phase 6**: Frontend Development (React + TypeScript + Vite + Tailwind)
7. **Phase 7**: DBMS Optimization Experiments, Documentation & Presentation Package

### Rules for Each Phase:
- Implement **only** the approved phase. Do not jump ahead.
- Run relevant test suites and inspect errors immediately.
- Fix all regressions before requesting approval for the next phase.
- Document all file changes, terminal commands executed, and known limitations.
