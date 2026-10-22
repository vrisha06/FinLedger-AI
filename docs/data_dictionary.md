# FinLedger-AI — Relational Data Dictionary

**Document:** Data Dictionary & Schema Specification
**Database Engine:** PostgreSQL 16
**Status:** Implemented & Verified in Phase 1
**Related Documents:** [implementation_plan.md](file:///c:/Users/Saksham%20Raj/Downloads/bin/Game,Project/Projects/FinLedger-AI/docs/implementation_plan.md), [database_invariants.md](file:///c:/Users/Saksham%20Raj/Downloads/bin/Game,Project/Projects/FinLedger-AI/docs/database_invariants.md)

---

## 1. Table: `users`
Represents system actors (Customers, Staff investigators, and System Administrators).

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `username` | `VARCHAR(50)` | No | — | **Unique**, Indexed |
| `email` | `VARCHAR(255)` | No | — | **Unique**, Indexed |
| `password_hash` | `VARCHAR(255)` | No | — | Argon2id / bcrypt password hash |
| `role` | `VARCHAR(20)` | No | `'CUSTOMER'` | `CHECK (role IN ('CUSTOMER', 'STAFF', 'ADMIN'))` |
| `is_active` | `BOOLEAN` | No | `TRUE` | Active account status flag |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of user creation |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of last user modification |

---

## 2. Table: `customers`
Customer demographic and KYC profile linked 1:1 with an authenticated User.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `user_id` | `UUID` | No | — | **Foreign Key** $\to$ `users(id)` (`ON DELETE RESTRICT`), **Unique** |
| `full_name` | `VARCHAR(100)` | No | — | Customer legal name |
| `phone` | `VARCHAR(20)` | Yes | `NULL` | Customer contact telephone number |
| `pan_number` | `VARCHAR(10)` | Yes | `NULL` | Indian Permanent Account Number |
| `kyc_status` | `VARCHAR(20)` | No | `'VERIFIED'` | `CHECK (kyc_status IN ('PENDING', 'VERIFIED', 'REJECTED'))` |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of profile registration |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of profile modification |

---

## 3. Table: `accounts`
Financial account entity holding cached balance and status.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `customer_id` | `UUID` | Yes | `NULL` | **Foreign Key** $\to$ `customers(id)` (`ON DELETE RESTRICT`), Indexed. Nullable for system clearing accounts. |
| `account_number` | `VARCHAR(32)` | No | — | **Unique**, Indexed (e.g. `INR-ACC-10001`, `INR-SYS-CLEARING`) |
| `account_type` | `VARCHAR(20)` | No | — | `CHECK (account_type IN ('SAVINGS', 'CURRENT', 'INTERNAL_CLEARING', 'INVESTMENT'))` |
| `currency` | `VARCHAR(3)` | No | `'INR'` | `CHECK (currency = 'INR')` |
| `cached_balance` | `NUMERIC(15, 2)` | No | `0.00` | Current balance. `CHECK (account_type = 'INTERNAL_CLEARING' OR cached_balance >= 0.00)` |
| `status` | `VARCHAR(20)` | No | `'ACTIVE'` | `CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED'))` |
| `version` | `INTEGER` | No | `1` | Optimistic concurrency / update sequence counter |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of account opening |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of last balance modification |

---

## 4. Table: `transfer_requests`
Master transfer record tracking idempotency keys, parameters, and lifecycle states.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `idempotency_key` | `VARCHAR(64)` | No | — | Client-provided token (UUIDv4), Indexed |
| `source_user_id` | `UUID` | No | — | **Foreign Key** $\to$ `users(id)` (`ON DELETE RESTRICT`), Indexed |
| `request_hash` | `VARCHAR(64)` | No | — | SHA-256 hash of canonical transfer parameters |
| `source_account_id` | `UUID` | No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE RESTRICT`), Indexed |
| `destination_account_id`| `UUID`| No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE RESTRICT`), Indexed |
| `amount` | `NUMERIC(15, 2)` | No | — | `CHECK (amount > 0.00)` |
| `currency` | `VARCHAR(3)` | No | `'INR'` | `CHECK (currency = 'INR')` |
| `status` | `VARCHAR(20)` | No | `'PENDING'` | `CHECK (status IN ('PENDING', 'POSTED', 'FAILED', 'REVERSED'))` |
| `failure_reason` | `TEXT` | Yes | `NULL` | Sanitized diagnostic error code / description |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of initial submission |
| `posted_at` | `TIMESTAMPTZ` | Yes | `NULL` | Timestamp of successful ledger commit |

**Table Constraints & Indexes**:
- `UNIQUE (source_user_id, idempotency_key)`: Scoped customer idempotency.
- `CHECK (source_account_id <> destination_account_id)`: Disallows transfer to identical account.
- Index: `idx_transfers_status_created (status, created_at DESC)`: Optimizes staff & audit chronological status search.
- Index: `ix_transfer_requests_source_account_id (source_account_id)`.
- Index: `ix_transfer_requests_destination_account_id (destination_account_id)`.

---

## 5. Table: `ledger_transactions`
Transaction header grouping balanced multi-row ledger legs.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `transfer_request_id` | `UUID` | Yes | `NULL` | **Foreign Key** $\to$ `transfer_requests(id)` (`ON DELETE RESTRICT`), **Unique** |
| `transaction_type` | `VARCHAR(30)` | No | — | `CHECK (transaction_type IN ('CUSTOMER_TRANSFER', 'INITIAL_DEPOSIT', 'CORRECTION_REVERSAL', 'INVESTMENT_PURCHASE'))` |
| `description` | `VARCHAR(255)` | No | — | Human-readable posting description |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of transaction creation |

---

## 6. Table: `ledger_entries`
Immutable double-entry posting legs (DEBIT or CREDIT). Strictly append-only.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `transaction_id` | `UUID` | No | — | **Foreign Key** $\to$ `ledger_transactions(id)` (`ON DELETE RESTRICT`), Indexed |
| `account_id` | `UUID` | No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE RESTRICT`) |
| `entry_type` | `VARCHAR(6)` | No | — | `CHECK (entry_type IN ('DEBIT', 'CREDIT'))` |
| `amount` | `NUMERIC(15, 2)` | No | — | `CHECK (amount > 0.00)` |
| `sequence_num` | `SMALLINT` | No | — | Order of leg execution within transaction |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of entry posting |

**Indexes & Triggers**:
- Index: `idx_ledger_entries_account_created_seq (account_id, created_at DESC, sequence_num DESC)`: Aligns with paginated ledger history query sort order, eliminating quicksort overhead.
- Trigger: `trg_verify_ledger_balance` (`CONSTRAINT TRIGGER AFTER INSERT OR UPDATE DEFERRABLE INITIALLY DEFERRED FOR EACH ROW`) asserting $\sum \text{Debits} - \sum \text{Credits} = 0$.
- Trigger: `trg_immutable_ledger_entries` (`BEFORE UPDATE OR DELETE`) raising exception.

---

## 7. Table: `audit_logs`
Immutable administrative, security, and financial event log. Strictly append-only.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | No | `auto` | **Primary Key** |
| `actor_user_id` | `UUID` | Yes | `NULL` | **Foreign Key** $\to$ `users(id)` (`ON DELETE RESTRICT`), Indexed |
| `action` | `VARCHAR(50)` | No | — | Event name (e.g. `AUTH_LOGIN`, `TRANSFER_FAILED`, `TRANSFER_POSTED`, `ALERT_RESOLVED`), Indexed |
| `entity_type` | `VARCHAR(30)` | No | — | Target entity domain (e.g. `USER`, `ACCOUNT`, `TRANSFER`, `ALERT`), Indexed |
| `entity_id` | `VARCHAR(64)` | No | — | Primary key of affected entity, Indexed |
| `ip_address` | `VARCHAR(45)` | Yes | `NULL` | Client IP address (IPv4 / IPv6) |
| `user_agent` | `VARCHAR(255)` | Yes | `NULL` | Client user-agent string |
| `metadata_json` | `JSONB` | No | `'{}'::jsonb` | Sanitized context payload (passwords/tokens redacted) |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Event timestamp, Indexed |

**Indexes & Triggers**:
- Index: `idx_audit_logs_action_created (action, created_at DESC)`.
- Trigger: `trg_immutable_audit_logs` (`BEFORE UPDATE OR DELETE`) raising exception.

---

## 8. Table: `fraud_predictions`
Advisory fraud scores, explainability snapshots, and staff triage status.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `transfer_request_id` | `UUID` | No | — | **Foreign Key** $\to$ `transfer_requests(id)` (`ON DELETE RESTRICT`), **Unique** |
| `model_version` | `VARCHAR(30)` | No | — | Model identifier (e.g. `rf-v1.0.0`) |
| `risk_score` | `NUMERIC(5, 4)` | No | — | `CHECK (risk_score >= 0.0000 AND risk_score <= 1.0000)` |
| `decision` | `VARCHAR(20)` | No | — | `CHECK (decision IN ('LOW_RISK', 'MEDIUM_RISK', 'HIGH_RISK'))` |
| `rule_flags` | `JSONB` | No | `'[]'::jsonb` | Triggered rule codes (e.g. `["RULE_VELOCITY_BURST"]`) |
| `feature_snapshot` | `JSONB` | No | `'{}'::jsonb` | Key feature values at time of transaction |
| `explanation` | `TEXT` | No | — | Human-readable explanation for staff investigators |
| `review_status` | `VARCHAR(20)` | No | `'PENDING'` | `CHECK (review_status IN ('PENDING', 'CLEARED', 'CONFIRMED_FRAUD', 'ESCALATED'))`, Indexed |
| `reviewed_by_user_id` | `UUID` | Yes | `NULL` | **Foreign Key** $\to$ `users(id)` (`ON DELETE RESTRICT`) |
| `review_notes` | `TEXT` | Yes | `NULL` | Mandatory notes recorded by reviewing staff |
| `reviewed_at` | `TIMESTAMPTZ` | Yes | `NULL` | Timestamp of review action |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of prediction generation, Indexed |

**Indexes**:
- Index: `idx_fraud_pending_risk (risk_score, created_at DESC)`.
- Index: `idx_fraud_pending_queue (risk_score DESC, created_at DESC) WHERE review_status = 'PENDING'`: Partial index targeting active triage queue.

---

## 9. Table: `financial_products`
Simulated financial investment offerings.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `name` | `VARCHAR(100)` | No | — | Product title (e.g. "90-Day Fixed Deposit") |
| `code` | `VARCHAR(32)` | No | — | **Unique**, Indexed (e.g. `FD-90D-2026`) |
| `product_type` | `VARCHAR(20)` | No | — | `CHECK (product_type IN ('FIXED_DEPOSIT', 'RECURRING_DEPOSIT', 'MUTUAL_FUND', 'TREASURY_BILL'))` |
| `annual_yield_rate` | `NUMERIC(5, 2)` | No | — | `CHECK (annual_yield_rate >= 0.00)` |
| `min_amount` | `NUMERIC(15, 2)` | No | — | `CHECK (min_amount > 0.00)` |
| `term_months` | `INTEGER` | No | — | `CHECK (term_months > 0)` |
| `is_active` | `BOOLEAN` | No | `TRUE` | Availability status |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Product addition timestamp |

---

## 10. Table: `investments`
Customer investment holdings linked to simulated products.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `customer_id` | `UUID` | No | — | **Foreign Key** $\to$ `customers(id)` (`ON DELETE RESTRICT`), Indexed |
| `account_id` | `UUID` | No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE RESTRICT`), Indexed |
| `product_id` | `UUID` | No | — | **Foreign Key** $\to$ `financial_products(id)` (`ON DELETE RESTRICT`), Indexed |
| `invested_amount` | `NUMERIC(15, 2)` | No | — | `CHECK (invested_amount > 0.00)` |
| `current_value` | `NUMERIC(15, 2)` | No | — | Current evaluated position |
| `status` | `VARCHAR(20)` | No | `'ACTIVE'` | `CHECK (status IN ('ACTIVE', 'MATURED', 'LIQUIDATED'))` |
| `start_date` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of investment commencement |
| `maturity_date` | `TIMESTAMPTZ` | No | — | Timestamp of maturity |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of investment creation |

---

## 11. Table: `payee_edges` (Innovation B: PayeeGuard)
Authoritative counterparty transfer relationships and volume aggregation.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `source_account_id` | `UUID` | No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE RESTRICT`), Indexed |
| `destination_account_id` | `UUID` | No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE RESTRICT`), Indexed |
| `transfer_count` | `INTEGER` | No | `1` | Historical completed transfers between counterparty pair |
| `total_amount` | `NUMERIC(15, 2)` | No | `0.00` | Cumulative transfer volume |
| `avg_amount` | `NUMERIC(15, 2)` | No | `0.00` | Historical average transfer size |
| `first_transfer_at` | `TIMESTAMPTZ` | No | `NOW()` | First recorded transfer timestamp |
| `last_transfer_at` | `TIMESTAMPTZ` | No | `NOW()` | Most recent transfer timestamp |

---

## 12. Table: `saved_payees` (Innovation B: PayeeGuard)
Customer-whitelisted beneficiaries with nickname and verification metadata.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `customer_id` | `UUID` | No | — | **Foreign Key** $\to$ `customers(id)` (`ON DELETE CASCADE`), Indexed |
| `account_id` | `UUID` | No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE RESTRICT`), Indexed |
| `nickname` | `VARCHAR(100)` | Yes | `NULL` | Customer-assigned display alias |
| `is_verified` | `BOOLEAN` | No | `TRUE` | Internal beneficiary directory validation flag |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Payee addition timestamp |

---

## 13. Table: `investigation_notes` (Innovation C: Forensic Dossier)
Staff forensic observations, hypotheses, and rationale notes linked to fraud alerts.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `fraud_prediction_id` | `UUID` | No | — | **Foreign Key** $\to$ `fraud_predictions(id)` (`ON DELETE CASCADE`), Indexed |
| `staff_user_id` | `UUID` | No | — | **Foreign Key** $\to$ `users(id)` (`ON DELETE RESTRICT`), Indexed |
| `note_type` | `VARCHAR(30)` | No | `'OBSERVATION'` | `CHECK (note_type IN ('OBSERVATION', 'HYPOTHESIS', 'CORROBORATING_EVIDENCE', 'RESOLUTION_RATIONALE'))` |
| `content` | `TEXT` | No | — | Forensic investigation commentary |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Note timestamp |

---

## 14. Table: `disputes` (Innovation C: Customer Recourse)
Formal customer transaction dispute records and investigation states.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `customer_id` | `UUID` | No | — | **Foreign Key** $\to$ `customers(id)` (`ON DELETE RESTRICT`), Indexed |
| `transfer_request_id` | `UUID` | No | — | **Foreign Key** $\to$ `transfer_requests(id)` (`ON DELETE RESTRICT`), Indexed |
| `category` | `VARCHAR(50)` | No | — | `CHECK (category IN ('UNAUTHORIZED', 'SUSPICIOUS_PAYEE', 'AMOUNT_DISCREPANCY', 'PROCESSING_DELAY', 'OTHER'))` |
| `description` | `TEXT` | No | — | Customer statement of issue |
| `status` | `VARCHAR(20)` | No | `'OPEN'` | `CHECK (status IN ('OPEN', 'INVESTIGATING', 'NEEDS_INFO', 'RESOLVED', 'REJECTED'))`, Indexed |
| `assigned_staff_id` | `UUID` | Yes | `NULL` | **Foreign Key** $\to$ `users(id)` (`ON DELETE SET NULL`) |
| `resolution_notes` | `TEXT` | Yes | `NULL` | Staff conclusion summary |
| `resolved_at` | `TIMESTAMPTZ` | Yes | `NULL` | Resolution timestamp |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Modification timestamp |

---

## 15. Table: `case_events` (Innovation C: Append-Only Recourse Timeline)
Immutable audit event sequence for customer dispute lifecycle.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `dispute_id` | `UUID` | No | — | **Foreign Key** $\to$ `disputes(id)` (`ON DELETE CASCADE`), Indexed |
| `actor_user_id` | `UUID` | No | — | **Foreign Key** $\to$ `users(id)` (`ON DELETE RESTRICT`), Indexed |
| `actor_role` | `VARCHAR(20)` | No | — | Role of initiating actor (`CUSTOMER`, `STAFF`, `ADMIN`) |
| `event_type` | `VARCHAR(50)` | No | — | Event classification (`DISPUTE_OPENED`, `STATUS_CHANGE`, `CUSTOMER_RESPONSE`, `RESOLVED`, `REJECTED`) |
| `from_status` | `VARCHAR(20)` | Yes | `NULL` | Prior status state |
| `to_status` | `VARCHAR(20)` | Yes | `NULL` | New status state |
| `notes` | `TEXT` | Yes | `NULL` | Commentary or rationale |
| `metadata_snapshot`| `JSONB` | No | `'{}'::jsonb` | Point-in-time context |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Immutable timestamp |

---

## 16. Table: `graph_findings` (Innovation A: LedgerGraph)
Persisted temporal money-flow pattern detections over relational ledger data.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `pattern_type` | `VARCHAR(50)` | No | — | `CHECK (pattern_type IN ('FAN_IN', 'FAN_OUT', 'RAPID_PASS_THROUGH', 'MULTI_HOP_LAYERING', 'CIRCULAR_WASH', 'BURST_VELOCITY'))` |
| `pattern_version` | `VARCHAR(20)` | No | — | Detector release version (e.g. `ledgergraph-v1.0.0`) |
| `severity` | `VARCHAR(20)` | No | — | `CHECK (severity IN ('INFO', 'SUSPICIOUS', 'CRITICAL'))` |
| `heuristic_score` | `NUMERIC(5, 4)` | No | — | `CHECK (heuristic_score >= 0.0000 AND heuristic_score <= 1.0000)` |
| `primary_account_id` | `UUID` | No | — | **Foreign Key** $\to$ `accounts(id)` (`ON DELETE CASCADE`), Indexed |
| `time_window_start` | `TIMESTAMPTZ` | No | — | Evaluation window lower bound |
| `time_window_end` | `TIMESTAMPTZ` | No | — | Evaluation window upper bound |
| `evidence_json` | `JSONB` | No | `'{}'::jsonb` | Participating transfers, amounts, timestamps, and hop paths |
| `explanation` | `TEXT` | No | — | Deterministic human explanation of pattern match |
| `review_status` | `VARCHAR(20)` | No | `'PENDING'` | `CHECK (review_status IN ('PENDING', 'CLEARED', 'CONFIRMED_FRAUD', 'ESCALATED'))`, Partial Indexed |
| `reviewed_by_user_id`| `UUID` | Yes | `NULL` | **Foreign Key** $\to$ `users(id)` (`ON DELETE SET NULL`) |
| `review_notes` | `TEXT` | Yes | `NULL` | Staff determination notes |
| `reviewed_at` | `TIMESTAMPTZ` | Yes | `NULL` | Review action timestamp |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Detection timestamp |

---

## 17. Table: `simulation_runs` (Innovation D: Fraud Lab)
Isolated synthetic benchmark runs and detector comparative evaluations.

| Column | PostgreSQL Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **Primary Key** |
| `scenario_name` | `VARCHAR(100)` | No | — | Evaluated synthetic pattern family |
| `seed` | `INTEGER` | No | — | Pseudorandom seed for fixed reproducibility |
| `sample_size` | `INTEGER` | No | — | Number of simulated transactions evaluated |
| `summary_metrics` | `JSONB` | No | `'{}'::jsonb` | Multi-detector precision, recall, F1, confusion matrices |
| `executed_by_user_id`| `UUID` | Yes | `NULL` | **Foreign Key** $\to$ `users(id)` (`ON DELETE SET NULL`) |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Benchmark execution timestamp |

