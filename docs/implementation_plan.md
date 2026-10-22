# FinLedger-AI — Master Implementation Plan

**Project Title:** FinLedger-AI: An Auditable Financial Transaction System with AI-Assisted Fraud Detection  
**Academic Context:** Database Systems B.Tech Capstone Project  
**Author:** Saksham Raj  
**Status:** Approved Architecture & Specification  

---

## 1. System Architecture & Component Responsibilities

FinLedger-AI follows a decoupled, three-tier enterprise architecture designed for relational data integrity, financial auditability, and transparent machine learning inference.

```mermaid
graph TB
    subgraph Client Tier ["Client Tier (React 19 + TypeScript + Vite + Tailwind CSS)"]
        CP[Customer Portal<br/>Accounts, Transfers, History, Products]
        SP[Staff & Risk Portal<br/>Alert Queue, Investigation Drawer, Audit Log, DBMS Lab]
    end

    subgraph API Tier ["Application Tier (Python 3.12 + FastAPI + Pydantic v2)"]
        Auth[Auth & RBAC Middleware<br/>JWT, Argon2id, Role Guards]
        TS[Transfer & Ledger Engine<br/>Canonical Locking, Idempotency, Double-Entry Posting]
        FS[Fraud Detection Service<br/>Rules Engine + Scikit-Learn Classifier + Explainability]
        AS[Audit Service<br/>Append-Only Event Logger]
        ES[DBMS Experiment Service<br/>EXPLAIN ANALYZE Runner & Buffer Stats]
    end

    subgraph Database Tier ["Database Tier (PostgreSQL 16)"]
        direction TB
        Accounts[(accounts & customers)]
        Transfers[(transfer_requests<br/>idempotency index)]
        Ledger[(ledger_transactions &<br/>ledger_entries<br/>Immutable + Deferrable Triggers)]
        Audit[(audit_logs<br/>Append-Only)]
        Fraud[(fraud_predictions & alerts)]
    end

    CP -->|REST API + Bearer Token| Auth
    SP -->|REST API + Bearer Token| Auth
    Auth --> TS
    Auth --> FS
    Auth --> AS
    Auth --> ES
    TS --> Accounts
    TS --> Transfers
    TS --> Ledger
    TS --> Audit
    FS --> Fraud
    AS --> Audit
    ES --> Ledger
```

### Component Breakdown
1. **Frontend (Client Tier)**:
   - **Customer Portal**: Account overview, balance lookups, transfer workflow with client-generated idempotency tokens (`UUIDv4`), transaction ledger history, product catalog (simulated fixed deposits).
   - **Staff & Risk Portal**: Triage queue for suspicious transactions, detailed alert investigation (feature importance breakdown, rule triggers, transaction graphs), staff decision logging, system-wide audit log inspector, and interactive DBMS execution plan visualizer.
2. **Backend (Application Tier - FastAPI)**:
   - **Layered Clean Architecture**:
     - `api/v1`: Route controllers, input validation schemas, response formatting.
     - `core`: Database session management, security (Argon2id, JWT), configuration (`pydantic-settings`).
     - `services`: Transactional orchestration (`TransferService`, `LedgerService`, `FraudService`, `AuditService`, `ExperimentService`).
     - `models`: SQLAlchemy 2.0 mapped declarative models with explicit column types, foreign key actions, and table check constraints.
3. **Database Tier (PostgreSQL)**:
   - Source of truth for all balances, postings, and audit trails.
   - Enforces ACID guarantees, row-level pessimistic locking (`SELECT ... FOR UPDATE`), uniqueness, check constraints, deferrable balance triggers, and ledger immutability triggers.
4. **Machine Learning & Analytics Subsystem**:
   - `ml/generator.py`: Synthetic transaction generator adhering to Benford's Law and diurnal banking cycles.
   - `ml/rules.py`: Transparent heuristic rule engine.
   - `ml/train.py` & `ml/evaluate.py`: Scikit-learn model training (`RandomForestClassifier`, `HistGradientBoostingClassifier`) with train/test separation, computing Precision, Recall, F1, ROC-AUC, and Confusion Matrix.

---

## 2. Repository & Folder Structure

```
FinLedger-AI/
├── .github/
│   └── workflows/ci.yml           # Automated pytest & linting pipeline
├── backend/
│   ├── alembic/
│   │   ├── versions/              # Numbered migration scripts
│   │   └── env.py
│   ├── alembic.ini
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py            # DB session & RBAC auth dependencies
│   │   │   └── v1/
│   │   │       ├── auth.py        # Login, logout, current user profile
│   │   │       ├── accounts.py    # Customer account details & balances
│   │   │       ├── transfers.py   # Transfer submission & status checks
│   │   │       ├── staff.py       # Alert triage, investigation & reports
│   │   │       ├── audit.py       # Append-only audit log inspection
│   │   │       ├── products.py    # Simulated financial products & investments
│   │   │       └── experiments.py # Live EXPLAIN ANALYZE benchmark runners
│   │   ├── core/
│   │   │   ├── config.py          # Environment settings via Pydantic
│   │   │   ├── database.py        # SQLAlchemy engine & session factory
│   │   │   ├── security.py        # Password hashing & JWT utilities
│   │   │   └── exceptions.py      # Domain exceptions & HTTP handlers
│   │   ├── models/
│   │   │   ├── base.py            # Declarative base & timestamp mixins
│   │   │   ├── user.py            # User & Role models
│   │   │   ├── customer.py        # Customer profile & KYC metadata
│   │   │   ├── account.py         # Account entity with cached balances
│   │   │   ├── transfer.py        # Transfer request & idempotency master
│   │   │   ├── ledger.py          # Double-entry ledger transactions & postings
│   │   │   ├── audit.py           # Immutable audit log entries
│   │   │   ├── product.py         # Financial products & investments
│   │   │   └── fraud.py           # Fraud prediction & alert records
│   │   ├── schemas/               # Pydantic v2 validation DTOs
│   │   ├── services/              # Business logic & transactional operations
│   │   └── main.py                # FastAPI application entrypoint
│   ├── ml/
│   │   ├── generator.py           # Reproducible synthetic transaction data generator
│   │   ├── features.py            # Feature engineering (rolling velocity, mean ratios)
│   │   ├── rules.py               # Rule-based fraud baseline
│   │   ├── train.py               # Model training pipeline
│   │   ├── evaluate.py            # Evaluation & confusion matrix generation
│   │   └── artifacts/             # Trained models, metrics.json, confusion_matrix.png
│   ├── tests/
│   │   ├── conftest.py            # Real PostgreSQL fixtures & rollback isolation
│   │   ├── test_auth.py           # Auth, password hashing, and RBAC tests
│   │   ├── test_transfers.py      # Transfer lifecycle, sufficient funds, rollback
│   │   ├── test_concurrency.py    # High-concurrency race condition & double-spend tests
│   │   ├── test_idempotency.py    # Idempotent replay & conflict verification
│   │   ├── test_immutability.py   # Trigger-enforced ledger & audit immutability
│   │   ├── test_reconciliation.py # Cached balance vs derived ledger sum verification
│   │   └── test_audit.py          # Action auditing & sensitive data redaction
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/            # Buttons, Inputs, Modals, Tables, Badges, Cards
│   │   │   ├── layout/            # Navigation, Sidebar, Topbar, Role Layouts
│   │   │   ├── customer/          # TransferModal, AccountCard, LedgerTable
│   │   │   └── staff/             # AlertTable, RiskBadge, ExplainDrawer, QueryTree
│   │   ├── context/               # AuthContext & Session management
│   │   ├── hooks/                 # Custom React hooks (useAuth, useTransfers)
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── customer/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── Accounts.tsx
│   │   │   │   ├── Transfers.tsx
│   │   │   │   ├── History.tsx
│   │   │   │   └── Products.tsx
│   │   │   └── staff/
│   │   │       ├── RiskOverview.tsx
│   │   │       ├── Alerts.tsx
│   │   │       ├── Investigation.tsx
│   │   │       ├── AuditLogs.tsx
│   │   │       └── DbExperiments.tsx
│   │   ├── services/api.ts        # Axios/Fetch client with interceptors
│   │   ├── types/index.ts         # TypeScript interfaces
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css              # Custom design system tokens
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── docker-compose.yml
├── .env.example
├── AGENTS.md                      # Persistent operational rules
├── README.md
└── docs/
    ├── er_diagram.mermaid
    ├── data_dictionary.md
    ├── architecture.md
    ├── database_invariants.md
    ├── phase_roadmap.md
    ├── implementation_plan.md
    ├── dbms_experiments.md
    ├── ai_model_evaluation.md
    └── demo_script.md
```

---

## 3. Entity-Relationship (ER) Diagram & Schema Proposal

```mermaid
erDiagram
    USERS ||--o| CUSTOMERS : "profiles"
    USERS ||--o{ AUDIT_LOGS : "acts_as"
    CUSTOMERS ||--o{ ACCOUNTS : "owns"
    ACCOUNTS ||--o{ TRANSFER_REQUESTS : "sources"
    ACCOUNTS ||--o{ TRANSFER_REQUESTS : "destines"
    ACCOUNTS ||--o{ LEDGER_ENTRIES : "posts_to"
    TRANSFER_REQUESTS ||--o| LEDGER_TRANSACTIONS : "posts_as"
    TRANSFER_REQUESTS ||--o| FRAUD_PREDICTIONS : "scored_by"
    LEDGER_TRANSACTIONS ||--|{ LEDGER_ENTRIES : "contains_legs"
    FRAUD_PREDICTIONS ||--o| USERS : "reviewed_by"
    CUSTOMERS ||--o{ INVESTMENTS : "holds"
    FINANCIAL_PRODUCTS ||--o{ INVESTMENTS : "underlies"

    USERS {
        uuid id PK
        varchar username UK
        varchar email UK
        varchar password_hash
        varchar role "CUSTOMER | STAFF | ADMIN"
        boolean is_active
        timestamptz created_at
    }

    CUSTOMERS {
        uuid id PK
        uuid user_id FK,UK
        varchar full_name
        varchar phone
        varchar pan_number
        varchar kyc_status "PENDING | VERIFIED | REJECTED"
        timestamptz created_at
    }

    ACCOUNTS {
        uuid id PK
        uuid customer_id FK "nullable for clearing"
        varchar account_number UK
        varchar account_type "SAVINGS | CURRENT | INTERNAL_CLEARING | INVESTMENT"
        varchar currency "INR"
        numeric cached_balance ">= 0 for customers"
        varchar status "ACTIVE | FROZEN | CLOSED"
        integer version
        timestamptz created_at
        timestamptz updated_at
    }

    TRANSFER_REQUESTS {
        uuid id PK
        varchar idempotency_key
        uuid source_user_id FK
        varchar request_hash
        uuid source_account_id FK
        uuid destination_account_id FK
        numeric amount "> 0"
        varchar currency "INR"
        varchar status "PENDING | POSTED | FAILED | REVERSED"
        text failure_reason
        timestamptz created_at
        timestamptz posted_at
    }

    LEDGER_TRANSACTIONS {
        uuid id PK
        uuid transfer_request_id FK,UK
        varchar transaction_type "CUSTOMER_TRANSFER | OPENING_DEPOSIT | REVERSAL"
        text description
        timestamptz created_at
    }

    LEDGER_ENTRIES {
        uuid id PK
        uuid transaction_id FK
        uuid account_id FK
        varchar entry_type "DEBIT | CREDIT"
        numeric amount "> 0"
        smallint sequence_num
        timestamptz created_at
    }

    AUDIT_LOGS {
        bigserial id PK
        uuid actor_user_id FK
        varchar action
        varchar entity_type
        varchar entity_id
        varchar ip_address
        jsonb metadata_json
        timestamptz created_at
    }

    FRAUD_PREDICTIONS {
        uuid id PK
        uuid transfer_request_id FK,UK
        varchar model_version
        numeric risk_score "0.0000 - 1.0000"
        varchar decision "LOW_RISK | MEDIUM_RISK | HIGH_RISK"
        jsonb rule_flags
        jsonb feature_snapshot
        text explanation
        varchar review_status "PENDING | CLEARED | CONFIRMED_FRAUD | ESCALATED"
        uuid reviewed_by_user_id FK
        text review_notes
        timestamptz reviewed_at
        timestamptz created_at
    }

    FINANCIAL_PRODUCTS {
        uuid id PK
        varchar name
        varchar code UK
        varchar product_type "FIXED_DEPOSIT | RECURRING_DEPOSIT | MUTUAL_FUND"
        numeric annual_yield_rate
        numeric min_amount
        integer term_months
        boolean is_active
    }

    INVESTMENTS {
        uuid id PK
        uuid customer_id FK
        uuid account_id FK
        uuid product_id FK
        numeric invested_amount
        numeric current_value
        varchar status "ACTIVE | MATURED | LIQUIDATED"
        timestamptz start_date
        timestamptz maturity_date
    }
```

### Detailed Schema Specifications

#### 1. `users`
- `id`: `UUID` Primary Key (`gen_random_uuid()`).
- `username`: `VARCHAR(50)` UNIQUE NOT NULL.
- `email`: `VARCHAR(255)` UNIQUE NOT NULL.
- `password_hash`: `VARCHAR(255)` NOT NULL.
- `role`: `VARCHAR(20)` NOT NULL (CHECK `role IN ('CUSTOMER', 'STAFF', 'ADMIN')`).
- `is_active`: `BOOLEAN` NOT NULL DEFAULT TRUE.
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().

#### 2. `customers`
- `id`: `UUID` Primary Key.
- `user_id`: `UUID` UNIQUE NOT NULL FK -> `users(id)` ON DELETE RESTRICT.
- `full_name`: `VARCHAR(100)` NOT NULL.
- `phone`: `VARCHAR(20)`.
- `pan_number`: `VARCHAR(10)` (Simulated Indian PAN format check).
- `kyc_status`: `VARCHAR(20)` NOT NULL DEFAULT 'VERIFIED' (CHECK `kyc_status IN ('PENDING', 'VERIFIED', 'REJECTED')`).
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().

#### 3. `accounts`
- `id`: `UUID` Primary Key.
- `customer_id`: `UUID` NULLABLE FK -> `customers(id)` ON DELETE RESTRICT (Nullable for system clearing/escrow accounts).
- `account_number`: `VARCHAR(20)` UNIQUE NOT NULL (e.g. `INR-ACC-10001`, `INR-SYS-CLEARING`).
- `account_type`: `VARCHAR(20)` NOT NULL (CHECK `account_type IN ('SAVINGS', 'CURRENT', 'INTERNAL_CLEARING', 'INVESTMENT')`).
- `currency`: `VARCHAR(3)` NOT NULL DEFAULT 'INR' (CHECK `currency = 'INR'`).
- `cached_balance`: `NUMERIC(15, 2)` NOT NULL DEFAULT 0.00 (CHECK `cached_balance >= 0.00` for customer accounts; clearing accounts can be unconstrained or signed).
- `status`: `VARCHAR(20)` NOT NULL DEFAULT 'ACTIVE' (CHECK `status IN ('ACTIVE', 'FROZEN', 'CLOSED')`).
- `version`: `INTEGER` NOT NULL DEFAULT 1 (Optimistic lock / change sequence counter).
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().

#### 4. `transfer_requests`
- `id`: `UUID` Primary Key.
- `idempotency_key`: `VARCHAR(64)` NOT NULL.
- `source_user_id`: `UUID` NOT NULL FK -> `users(id)`.
- `request_hash`: `VARCHAR(64)` NOT NULL (SHA-256 hash of `source_account_id + destination_account_id + amount + currency + memo`).
- `source_account_id`: `UUID` NOT NULL FK -> `accounts(id)`.
- `destination_account_id`: `UUID` NOT NULL FK -> `accounts(id)`.
- `amount`: `NUMERIC(15, 2)` NOT NULL (CHECK `amount > 0.00`).
- `currency`: `VARCHAR(3)` NOT NULL DEFAULT 'INR'.
- `status`: `VARCHAR(20)` NOT NULL (CHECK `status IN ('PENDING', 'POSTED', 'FAILED', 'REVERSED')`).
- `failure_reason`: `TEXT` NULLABLE.
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().
- `posted_at`: `TIMESTAMPTZ` NULLABLE.
- **Constraints**:
  - `UNIQUE(source_user_id, idempotency_key)`: Scoped idempotency per authenticated customer.
  - `CHECK(source_account_id <> destination_account_id)`: Cannot transfer to identical account.

#### 5. `ledger_transactions`
- `id`: `UUID` Primary Key.
- `transfer_request_id`: `UUID` NULLABLE FK -> `transfer_requests(id)`.
- `transaction_type`: `VARCHAR(30)` NOT NULL (CHECK `transaction_type IN ('CUSTOMER_TRANSFER', 'OPENING_DEPOSIT', 'CORRECTION_REVERSAL', 'INVESTMENT_PURCHASE')`).
- `description`: `VARCHAR(255)` NOT NULL.
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().

#### 6. `ledger_entries`
- `id`: `UUID` Primary Key.
- `transaction_id`: `UUID` NOT NULL FK -> `ledger_transactions(id)` ON DELETE RESTRICT.
- `account_id`: `UUID` NOT NULL FK -> `accounts(id)` ON DELETE RESTRICT.
- `entry_type`: `VARCHAR(6)` NOT NULL (CHECK `entry_type IN ('DEBIT', 'CREDIT')`).
- `amount`: `NUMERIC(15, 2)` NOT NULL (CHECK `amount > 0.00`).
- `sequence_num`: `SMALLINT` NOT NULL (1 for debit, 2 for credit, or multi-leg sequence).
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().

#### 7. `audit_logs`
- `id`: `BIGSERIAL` Primary Key.
- `actor_user_id`: `UUID` NULLABLE FK -> `users(id)`.
- `action`: `VARCHAR(50)` NOT NULL (e.g. `AUTH_LOGIN`, `TRANSFER_POSTED`, `ALERT_RESOLVED`, `ACCOUNT_STATUS_CHANGE`, `REVERSAL_INITIATED`).
- `entity_type`: `VARCHAR(30)` NOT NULL (e.g. `USER`, `ACCOUNT`, `TRANSFER`, `ALERT`).
- `entity_id`: `VARCHAR(64)` NOT NULL.
- `ip_address`: `VARCHAR(45)` NULLABLE.
- `user_agent`: `VARCHAR(255)` NULLABLE.
- `metadata_json`: `JSONB` NOT NULL DEFAULT '{}'::jsonb (Safe context: before/after status, transfer amount, rule triggers; strictly sanitizing passwords/tokens).
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().

#### 8. `fraud_predictions` & `fraud_alerts`
- `id`: `UUID` Primary Key.
- `transfer_request_id`: `UUID` NOT NULL FK -> `transfer_requests(id)`.
- `model_version`: `VARCHAR(30)` NOT NULL (e.g. `heuristic_rules_v1`, `random_forest_v1`).
- `risk_score`: `NUMERIC(5, 4)` NOT NULL (Range `0.0000` to `1.0000`).
- `decision`: `VARCHAR(20)` NOT NULL (CHECK `decision IN ('LOW_RISK', 'MEDIUM_RISK', 'HIGH_RISK')`).
- `rule_flags`: `JSONB` NOT NULL DEFAULT '[]'::jsonb (e.g. `["VELOCITY_EXCEEDED", "AMOUNT_SPIKE"]`).
- `feature_snapshot`: `JSONB` NOT NULL DEFAULT '{}'::jsonb (historical mean, velocity count, time delta, location delta).
- `explanation`: `TEXT` NOT NULL (Human-readable rationale for staff).
- `review_status`: `VARCHAR(20)` NOT NULL DEFAULT 'PENDING' (CHECK `review_status IN ('PENDING', 'CLEARED', 'CONFIRMED_FRAUD', 'ESCALATED')`).
- `reviewed_by_user_id`: `UUID` NULLABLE FK -> `users(id)`.
- `review_notes`: `TEXT` NULLABLE.
- `reviewed_at`: `TIMESTAMPTZ` NULLABLE.
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW().

#### 9. `financial_products` & `investments`
- `financial_products`: `id`, `name`, `code`, `product_type` (`FIXED_DEPOSIT`, `MUTUAL_FUND`, `TREASURY_BILL`), `annual_yield_rate` (`NUMERIC(5,2)`), `min_amount`, `term_months`, `is_active`.
- `investments`: `id`, `customer_id`, `account_id`, `product_id`, `invested_amount`, `current_value`, `status` (`ACTIVE`, `MATURED`, `LIQUIDATED`), `start_date`, `maturity_date`, `created_at`.

---

## 4. Double-Entry Ledger & Account Balance Strategy

### Accounting Convention
In banking accounting:
- Customer savings and current accounts are **Liabilities** (money owed to depositors).
- Internal clearing and cash accounts are **Assets** or clearing reserves.

For an ordinary customer transfer from Account A to Account B of ₹1,000.00:
1. **Debit Account A** for ₹1,000.00 (Reduces liability to Customer A $\to$ decreases Account A balance).
2. **Credit Account B** for ₹1,000.00 (Increases liability to Customer B $\to$ increases Account B balance).
$$\sum \text{Debits} (1,000.00) = \sum \text{Credits} (1,000.00)$$

For an opening balance / simulated initial deposit of ₹50,000.00:
1. **Debit Internal Clearing Account** (`INR-SYS-CLEARING`) for ₹50,000.00.
2. **Credit Customer Account** for ₹50,000.00.
$$\sum \text{Debits} = \sum \text{Credits} = 50,000.00$$
*No money is ever manufactured by an arbitrary SQL `UPDATE accounts SET balance = ...`.*

### Derived Balance vs. Cached Balance Strategy
- **Source of Truth**: The derived sum of ledger postings:
  $$\text{Derived Balance} = \sum_{entry \in \text{CREDIT}} amount - \sum_{entry \in \text{DEBIT}} amount$$
- **High-Performance Cached Balance**: `accounts.cached_balance` is maintained **atomically** in the same transaction as the ledger postings.
- **Reconciliation Engine**: An automated background verification worker and integration test compares `cached_balance` against the derived ledger sum for every account:
  ```sql
  SELECT a.id, a.account_number, a.cached_balance,
         COALESCE(SUM(CASE WHEN le.entry_type = 'CREDIT' THEN le.amount ELSE -le.amount END), 0) AS derived_balance
  FROM accounts a
  LEFT JOIN ledger_entries le ON a.id = le.account_id
  GROUP BY a.id, a.account_number, a.cached_balance
  HAVING a.cached_balance <> COALESCE(SUM(CASE WHEN le.entry_type = 'CREDIT' THEN le.amount ELSE -le.amount END), 0);
  ```
  Any returned rows indicate an integrity violation.

### Transaction Balanced Integrity Assertion
In PostgreSQL, row-level `CHECK` constraints cannot run aggregate queries across multiple rows. We enforce balance integrity at two levels:
1. **Service Layer**: In Python, verify that within the transaction before commit, `sum(debits) == sum(credits)`; abort and rollback if unequal.
2. **Database Layer**: A PostgreSQL `CONSTRAINT TRIGGER` (`DEFERRABLE INITIALLY DEFERRED`) on `ledger_entries` executed at transaction commit that validates:
   ```sql
   SELECT SUM(CASE WHEN entry_type = 'DEBIT' THEN amount ELSE -amount END)
   FROM ledger_entries WHERE transaction_id = NEW.transaction_id;
   ```
   If this sum != 0, PostgreSQL raises an exception and automatically rolls back the entire transaction.

---

## 5. Transfer Transaction Lifecycle & State Transitions

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    participant API as FastAPI API
    participant TransferSvc as TransferService
    participant DB as PostgreSQL 16
    participant FraudSvc as FraudDetectionService
    participant AuditSvc as AuditService

    Customer->>API: POST /transfers (Payload + Idempotency-Key)
    API->>TransferSvc: execute_transfer(user, payload, idempotency_key)
    
    rect rgb(240, 245, 255)
        note over TransferSvc, DB: 1. Idempotency Check & Pre-Flight
        TransferSvc->>DB: Check idempotency (source_user_id, key)
        alt Key exists with SAME hash
            DB-->>TransferSvc: Existing transfer record
            TransferSvc-->>API: 200/201 OK (Idempotent Cached Result)
        else Key exists with DIFFERENT hash
            TransferSvc-->>API: 409 Conflict (Mismatched Payload)
        end
    end

    rect rgb(255, 245, 245)
        note over TransferSvc, DB: 2. Financial Transaction (financial_txn BEGIN)
        TransferSvc->>DB: Lock accounts in canonical order<br/>SELECT ... WHERE id IN (min_id, max_id) ORDER BY id FOR UPDATE
        DB-->>TransferSvc: Locked account rows (source, destination)

        TransferSvc->>TransferSvc: Validate source ownership, ACTIVE status & available balance >= amount
        alt Insufficient Funds / Invalid State
            note over TransferSvc, DB: Rollback financial_txn (No balances changed, no ledger legs persisted)
            TransferSvc->>DB: ROLLBACK financial_txn
            
            rect rgb(255, 250, 240)
                note over TransferSvc, DB: 2b. Independent Audit Transaction (audit_txn BEGIN)
                TransferSvc->>DB: Insert transfer_requests (status='FAILED', reason='INSUFFICIENT_FUNDS')
                TransferSvc->>AuditSvc: Insert audit_logs (action='TRANSFER_FAILED', metadata)
                TransferSvc->>DB: COMMIT audit_txn (Audit trail preserved forever!)
            end
            TransferSvc-->>API: 422 Unprocessable Entity (Failure receipt with cached key)
        end

        TransferSvc->>DB: Insert ledger_transactions record
        TransferSvc->>DB: Insert Leg 1: DEBIT source_account
        TransferSvc->>DB: Insert Leg 2: CREDIT destination_account
        TransferSvc->>DB: Update cached_balance on source & destination
        TransferSvc->>DB: Insert/Update transfer_requests (status='POSTED')
        note over DB: COMMIT financial_txn (Deferrable Trigger asserts Debits == Credits)
        DB-->>TransferSvc: Financial Transaction Committed
    end

    rect rgb(245, 255, 245)
        note over TransferSvc, FraudSvc: 3. Post-Commit Advisory Scoring & Audit Log
        TransferSvc->>AuditSvc: log_action(actor=user, action='TRANSFER_POSTED')
        TransferSvc->>FraudSvc: assess_transfer_risk(transfer_id)
        FraudSvc->>DB: Insert fraud_predictions & alert (if high risk)
    end

    TransferSvc-->>API: 201 Created (Transfer Receipt)
    API-->>Customer: Transfer confirmed with receipt & new balance
```

---

## 6. Concurrency Control & Idempotency Strategy

### Canonical Row Locking
To eliminate deadlocks caused by bi-directional transfers occurring concurrently (e.g., User 1 transferring from A $\to$ B while User 2 transfers from B $\to$ A):
- The service sorts the account primary keys:
  $$\text{first\_id} = \min(A, B), \quad \text{second\_id} = \max(A, B)$$
- Executes:
  ```sql
  SELECT id, cached_balance, status, customer_id
  FROM accounts
  WHERE id IN (:first_id, :second_id)
  ORDER BY id
  FOR UPDATE;
  ```
Because all concurrent transactions acquire row locks in the identical lexicographical order, circular lock-wait graphs (deadlocks) are mathematically prevented.

### Preventing Double-Spending Under High Concurrency
If two requests attempt to spend ₹600 from an account with only ₹1,000 available:
1. Request 1 acquires the lock on the account row.
2. Request 2 blocks waiting for the row lock.
3. Request 1 checks available balance (₹1,000 $\ge$ ₹600), deducts ₹600 (balance $\to$ ₹400), inserts ledger postings, and commits.
4. Request 2 unblocks, reads the freshly committed balance of ₹400, checks available balance (₹400 $\ge$ ₹600 $\to$ **FALSE**), raises `InsufficientFundsError`, and cleanly rolls back.
5. The account balance is never overdrawn, and debits match credits exactly.

### Scoped Idempotency
- **Header**: `Idempotency-Key: <UUIDv4>`
- **Scope**: Evaluated per authenticated customer `(source_user_id, idempotency_key)`.
- **Payload Hash**: SHA-256 of canonical JSON payload:
  `sha256(source_account_id + destination_account_id + amount + currency + memo)`
- If a client retries after a network timeout, the server returns the existing transaction without executing a duplicate debit. If the key is reused with modified parameters, the API rejects it with `409 Conflict`.

---

## 7. Authentication, Authorization & Security Architecture

1. **Password Hashing**: Argon2id or bcrypt (cost factor 12) via `passlib[bcrypt]`. Plaintext passwords never touch logs or database records.
2. **Token Security**: Cryptographically signed JSON Web Tokens (`HS256`, 60-minute expiry) containing `sub` (User ID), `role`, and `username`.
3. **Role-Based Access Control (RBAC)**:
   - `ROLE_CUSTOMER`: Access restricted strictly to owned accounts, personal transfer execution, and personal ledger history.
   - `ROLE_STAFF`: Read access to all accounts and transfers, access to fraud alert queues, alert review actions, and investigation dashboards.
   - `ROLE_ADMIN`: All staff permissions plus user provisioning, audit log export, and DBMS benchmark execution.
4. **Server-Side Ownership Enforcement**:
   - Every customer endpoint queries accounts filtered by `account.customer.user_id == current_user.id`.
   - Never rely on frontend assertions or client-supplied customer identifiers.

---

## 8. API Endpoint Specification

### Auth & User Management
- `POST /api/v1/auth/login`: Authenticate credentials, return access token & user profile.
- `POST /api/v1/auth/logout`: Audit logout event.
- `GET  /api/v1/auth/me`: Retrieve current user profile and role.

### Customer Operations
- `GET  /api/v1/accounts`: List accounts owned by current customer with balances.
- `GET  /api/v1/accounts/{id}`: Detailed account information (cached balance, status, currency).
- `GET  /api/v1/accounts/{id}/ledger`: Paginated ledger postings (credits, debits, counterparty, running balance).
- `POST /api/v1/transfers`: Execute transfer with `Idempotency-Key` header.
- `GET  /api/v1/transfers/{id}`: Fetch transfer status, execution timestamp, and receipt.
- `GET  /api/v1/products`: Catalog of simulated financial products (Fixed Deposits, Liquid Funds).
- `GET  /api/v1/investments`: List customer's simulated investments.
- `POST /api/v1/investments`: Purchase a simulated investment via double-entry debit from savings.

### Staff & Risk Operations
- `GET  /api/v1/staff/risk-overview`: Metrics on total volume, flagged transactions, pending reviews.
- `GET  /api/v1/staff/alerts`: Filterable alert queue (status, severity, date range, customer).
- `GET  /api/v1/staff/alerts/{id}`: Comprehensive investigation packet (rule flags, model risk score, feature weights, historical transfer graph).
- `POST /api/v1/staff/alerts/{id}/review`: Record staff decision (`CLEARED`, `CONFIRMED_FRAUD`, `ESCALATED`) with mandatory `review_notes`.
- `GET  /api/v1/staff/transactions`: Global transaction search with multi-column filtering.

### Audit & DBMS Experiments
- `GET  /api/v1/audit/logs`: Paginated, filterable audit log viewer with actor attribution.
- `GET  /api/v1/audit/reconciliation`: Execute real-time system balance reconciliation.
- `GET  /api/v1/experiments/query-plans`: Live `EXPLAIN (ANALYZE, BUFFERS)` execution of indexed vs unindexed queries.
- `POST /api/v1/experiments/seed-synthetic`: Seed configurable synthetic transaction volume (1k to 100k+).

---

## 9. UI Page & Navigation Plan

Built with React, TypeScript, Vite, and Tailwind CSS using a sleek fintech visual language (dark slate palette, emerald/amber/rose financial accents, tabular figures, and responsive navigation).

```
Customer Portal Navigation:
├── Dashboard       (/dashboard)      -> Net worth card, account cards, recent activity, quick transfer
├── Accounts        (/accounts)       -> Detailed cards, account numbers, balance breakdowns
├── Transfers       (/transfers)      -> Transfer wizard (form -> preview -> idempotent receipt)
├── History         (/history)        -> Ledger entries table, date/type filter, CSV export
└── Investments     (/products)       -> FD catalog, interest calculator, active investments

Staff Portal Navigation:
├── Risk Overview   (/staff/risk)     -> Real-time KPI counters, alert distribution charts
├── Alert Queue     (/staff/alerts)   -> Triage table with severity badges (High/Med/Low) & status filters
├── Investigation   (/staff/alerts/:id)-> Deep dive: AI feature explanation, rule triggers, decision form
│                                        [Options: CLEARED (False Positive), CONFIRMED_FRAUD, ESCALATED]
├── Transactions    (/staff/txns)     -> Search all customer transfers across system
├── Audit Trail     (/staff/audit)    -> Tamper-evident log with JSON metadata inspector
└── DBMS Lab        (/staff/dbms)     -> Interactive EXPLAIN ANALYZE comparison tool
```

---

## 10. Synthetic Fraud Dataset & Machine Learning Plan

### 1. Synthetic Data Generator (`backend/ml/generator.py`)
- **Reproducibility**: Parameterized random seed.
- **Scale**: Configurable 1,000 to 100,000+ transactions across 500+ synthetic customers.
- **Realism**:
  - Amounts follow Benford's Law and log-normal distributions.
  - Realistic diurnal curves (active hours 08:00 to 22:00 IST).
- **Injected Fraud Scenarios (~2-3% prevalence)**:
  1. **Velocity Spikes**: 4+ high-value transfers within 5 minutes to new counterparty accounts.
  2. **Sudden Outlier Amounts**: Transfers exceeding 6-8x of the customer's 30-day moving average.
  3. **Rapid Depletion (Drain)**: Account balance drawn down to < ₹100 within 20 minutes of initial deposit.
  4. **Structuring (Smurfing)**: Multiple repeated transfers just below reporting thresholds (e.g. ₹49,000).

### 2. Transparent Rule Baseline (`backend/ml/rules.py`)
- Rule 1: `VELOCITY_ALERT` (Count of transfers in last 10 min > 3).
- Rule 2: `ZSCORE_OUTLIER` (Amount > 4 standard deviations from customer historical mean).
- Rule 3: `RAPID_DRAIN` (Transfer > 90% of account balance within 1 hour of account creation).
- Rule 4: `OFF_HOURS_HIGH_VALUE` (Amount > ₹100,000 between 01:00 AM and 05:00 AM).

### 3. Machine Learning Models & Evaluation (`backend/ml/evaluate.py`)
- **Feature Extraction**:
  - `amount_to_avg_ratio`: Current amount / 30-day customer average.
  - `rolling_count_1h`, `rolling_sum_1h`: Activity velocity in the preceding 60 minutes.
  - `is_first_time_counterparty`: Binary flag indicating novel destination account.
  - `balance_drain_pct`: Current amount / current available balance.
  - `hour_sin`, `hour_cos`: Cyclical temporal representations.
- **Models**:
  - `RandomForestClassifier(n_estimators=100, class_weight='balanced')`
  - `HistGradientBoostingClassifier(class_weight='balanced')`
- **Evaluation Protocol**:
  - 70% Train, 15% Validation, 15% Out-of-time Test split.
  - Side-by-side metric comparison: **Rule Baseline vs Random Forest vs Gradient Boosting**.
  - Metrics computed: Precision, Recall, F1-Score, ROC-AUC, PR-AUC, and Confusion Matrix.
  - Output saved to `ml/artifacts/evaluation_report.json` and plotted to `confusion_matrix.png`.
- **Academic Disclaimer**:
  *All reports and UI headers will explicitly state that synthetic benchmark results evaluate model behavior against synthetic generation assumptions and do not represent production performance against real-world adversarial banking fraud.*

---

## 11. Test Matrix & DBMS Experiments

### Automated Test Matrix (`pytest`)
| Test Category | File | Description & Assertion |
| :--- | :--- | :--- |
| **Authentication** | `test_auth.py` | Validates Argon2id hashing, token expiry, customer vs staff RBAC blocking. |
| **Transfer Lifecycle** | `test_transfers.py` | Successful debit/credit posting; insufficient funds rollback; same-account transfer rejection; forced exception rollback verifying zero partial postings. |
| **Ledger Integrity** | `test_ledger_integrity.py` | Asserts sum of debits == sum of credits; deferrable trigger aborts unbalanced inserts; immutability trigger blocks SQL `UPDATE` / `DELETE` on postings. |
| **Concurrency & Race Conditions** | `test_concurrency.py` | 10 concurrent threads attempting to withdraw ₹500 from a ₹1,000 account (exact 2 succeed, 8 fail, balance=₹0.00); 20 bi-directional transfers (A $\leftrightarrow$ B) run with zero deadlocks. |
| **Scoped Idempotency** | `test_idempotency.py` | Repeated request with identical key returns cached 200/201 response; request with identical key but altered amount returns 409 Conflict. |
| **Reconciliation** | `test_reconciliation.py` | Iterates all accounts and asserts `cached_balance == sum(credits) - sum(debits)`. |
| **Audit Trails** | `test_audit.py` | Verifies append-only logs for logins, transfers, and staff decisions; confirms absence of plaintext passwords or tokens. |

### DBMS Performance Experiments Methodology (`docs/dbms_experiments.md`)

> [!IMPORTANT]
> **Illustrative Estimates Notice**: All performance figures, query timings, and buffer statistics discussed during planning are **illustrative target estimates and methodological baselines only**, not measured results. Actual empirical measurements, execution plans, and buffer statistics will be captured and documented in `docs/dbms_experiments.md` using `EXPLAIN (ANALYZE, BUFFERS)` on the synthesized PostgreSQL dataset during Phase 7. Under the persistent engineering rules, no benchmark numbers will be fabricated or claimed without verified execution.

1. **Target Experiment 1: Customer Account Ledger History**:
   - Query: `SELECT * FROM ledger_entries WHERE account_id = :acc ORDER BY created_at DESC LIMIT 20;`
   - Evaluation Method: Measure execution time and buffer read stats using `EXPLAIN (ANALYZE, BUFFERS)` before adding index (Seq Scan baseline) and after adding composite index `idx_ledger_entries_account_created (account_id, created_at DESC)`.
2. **Target Experiment 2: Staff Multi-Filter Transaction Search**:
   - Query: `SELECT * FROM transfer_requests WHERE status = 'POSTED' AND amount >= :min_amt AND created_at >= :start_date;`
   - Evaluation Method: Compare cost and plan tree of unindexed filter scan vs partial index `idx_transfers_posted_created_amount ON transfer_requests(created_at, amount) WHERE status = 'POSTED'`.
3. **Target Experiment 3: Pending High-Risk Alert Triage**:
   - Query: `SELECT * FROM fraud_predictions WHERE review_status = 'PENDING' AND risk_score >= 0.70 ORDER BY created_at DESC;`
   - Evaluation Method: Compare full scan cost against filtered index `idx_fraud_pending_risk ON fraud_predictions(risk_score, created_at DESC) WHERE review_status = 'PENDING'`.

---

## 12. Phased Implementation Roadmap

```mermaid
gantt
    title FinLedger-AI Phased Implementation Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: DB & Foundation
    Schema, Migrations, Constraints, Triggers   :p1, 2026-10-10, 1d
    section Phase 2: Auth & RBAC
    User models, JWT, Argon2id, Audit Logger    :p2, after p1, 1d
    section Phase 3: Core Ledger Engine
    TransferService, Canonical Locks, Idempotency:p3, after p2, 1d
    Concurrency & Reconciliation Tests          :p3b, after p3, 1d
    section Phase 4: ML & Fraud Subsystem
    Synthetic Generator, Rules Baseline, Models :p4, after p3b, 1d
    Evaluation metrics & Advisory Alert Hook    :p4b, after p4, 1d
    section Phase 5: Products & Reports
    Financial Products, Investments, Aggregations:p5, after p4b, 1d
    section Phase 6: Frontend Development
    Customer Portal & Transfer Flow             :p6a, after p5, 1d
    Staff Portal, Investigation & DBMS Lab       :p6b, after p6a, 1d
    section Phase 7: Experiments & Presentation
    Live EXPLAIN ANALYZE Benchmarks, Demo Script:p7, after p6b, 1d
```

### Milestones & Acceptance Criteria:
- **Phase 1: Database Foundation & Migrations**:
  - Acceptance: Alembic migrations apply cleanly; tables, check constraints, deferrable balance triggers, and immutability triggers verified.
- **Phase 2: Authentication, Authorization & Audit**:
  - Acceptance: JWT login/logout works; customer and staff roles enforced; audit log records security events without sensitive leaks.
- **Phase 3: Core Ledger Engine & Concurrency Safety**:
  - Acceptance: Transfers post balanced debit/credit legs; concurrent withdrawals prevent double-spending; bi-directional transfers prevent deadlocks; idempotency replays/conflicts handled; reconciliation test passes 100%.
- **Phase 4: Synthetic Data & Machine Learning Pipeline**:
  - Acceptance: Synthetic generator produces 20k+ realistic records; rule baseline and ML model trained; Precision/Recall/F1/Confusion matrix evaluated and exported; advisory fraud alerts populate staff queue.
- **Phase 5: Financial Products & Investment Ledger**:
  - Acceptance: Product catalog available; investment purchase executes double-entry debit from customer account; portfolio balances reflect real ledger state.
- **Phase 6: Modern Fintech Web Application**:
  - Acceptance: Responsive React UI with distinct Customer and Staff portals; live API integration (zero mocked responses); transfer confirmation flow; investigation drawer with AI explanation; DBMS query plan viewer.
- **Phase 7: DBMS Experiments, Documentation & Presentation Package**:
  - Acceptance: `EXPLAIN (ANALYZE, BUFFERS)` benchmarks documented with execution plans; complete presentation demo script, ER diagram, data dictionary, and test reports compiled.

---

## 13. Technical Assumptions, Risks & Deferred Features

### Environment & Database Strategy (Native PostgreSQL First-Class, Docker Optional)
- **Host Environment State**: Docker is currently not installed on the host system PATH. Python 3.12, Node.js 24, npm, and Windows Package Manager (`winget`) are verified available.
- **Dual Support Strategy**:
  1. **Native Local PostgreSQL (Primary / First-Class Target)**:
     - FinLedger-AI fully supports running against a native local PostgreSQL 16+ instance on Windows (installed via `winget install PostgreSQL.PostgreSQL` or the standard EDB PostgreSQL Windows installer).
     - Automated PowerShell scripts (`scripts/setup_postgres_local.ps1` and `scripts/init_db.ps1`) will automate test and development database provisioning (`finledger` and `finledger_test`), role creation, and schema migration without requiring Docker.
     - Environment configuration is driven by `.env` (e.g., `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finledger`).
  2. **Docker Compose (Optional Portability Alternative)**:
     - A standard `docker-compose.yml` is provided for developers who prefer containerized PostgreSQL and pgAdmin, but Docker is strictly **optional** and never a prerequisite for running or testing the system.

### Deferred Features (Scope Boundaries)
To ensure the project prioritizes database correctness, financial invariants, and automated verification:
1. **Real-world payment gateway integrations (Razorpay, Stripe)**: Excluded by design; the system is an educational double-entry ledger operating on simulated INR.
2. **Multi-currency forex exchange**: Excluded in initial scope (single currency INR only) to maintain ledger simplicity.
3. **Natural language to SQL (NL2SQL) or conversational chatbot assistants**: Deferred so that development focuses squarely on deterministic relational modeling, concurrency safety, and transparent ML classification.
