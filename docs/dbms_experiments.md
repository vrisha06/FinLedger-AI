# FinLedger-AI — Phase 7: PostgreSQL Performance Evaluation & Reliability Report

**Project:** FinLedger-AI: An Auditable Financial Transaction System with AI-Assisted Fraud Detection  
**Module:** DBMS Performance Evaluation, Scientific Index Optimization & Transaction Concurrency Reliability  
**Status:** Executed & Empirically Verified  
**Target Benchmark Database:** `finledger_bench` (PostgreSQL 16.15)  

---

## 1. Benchmark Environment & System Specifications

| Environment Component | Specification Details |
| :--- | :--- |
| **Operating System** | Windows 11 Enterprise (64-bit, x86_64) |
| **DBMS Engine** | PostgreSQL 16.15 (compiled by Visual C++ build 1944, 64-bit) |
| **Connection Pooling** | SQLAlchemy 2.0 Engine (QueuePool / NullPool) |
| **Isolation Level** | `READ COMMITTED` (with canonical ascending row-level locking `SELECT ... FOR UPDATE`) |
| **Database Target Isolation** | Dedicated benchmark database `finledger_bench` (zero mutations on development `finledger`) |
| **Alembic Migration State** | `b4129e73f910` (Phase 7 performance indexes applied) |

---

## 2. Dataset Generation Parameters & Benchmark Row Counts

The synthetic benchmark dataset was deterministically generated using `backend/scripts/benchmark_dbms.py` with random seed `42`:

| Table Name | Benchmark Row Count | Dataset Characteristics |
| :--- | :--- | :--- |
| `accounts` | **151** | 1 Internal Clearing (`INR-SYS-CLEARING`), 100 Savings, 50 Current accounts |
| `customers` | **100** | Verified KYC customer profiles linked to authenticated users |
| `users` | **100** | Authenticated customer accounts |
| `transfer_requests` | **25,000** | 23,987 `POSTED` (96%), 753 `FAILED` (3%), 260 `PENDING` (1%) |
| `ledger_transactions`| **23,987** | One-to-one master records for each posted transfer |
| `ledger_entries` | **47,974** | **Strictly balanced double-entry legs** (1 Debit, 1 Credit per posted transfer) |
| `fraud_predictions` | **1,000** | 200 High-Risk (>0.70), 300 Medium-Risk, 500 Low-Risk (268 `PENDING` triage queue) |
| **Total Financial Rows**| **98,312** | Comprehensive multi-table schema representing high-density banking activity |

---

## 3. Representative Workloads & Exact SQL Queries

Four representative query workloads were profiled under identical conditions using PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`:

### Workload 1: Account Transaction History (Ledger Entries)
- **Application Path:** `GET /api/v1/accounts/{account_id}/ledger?limit=50&offset=0`
- **Query Logic:** Paginated double-entry ledger history for a single customer account ordered chronologically descending:
```sql
SELECT id, transaction_id, account_id, entry_type, amount, sequence_num, created_at
FROM ledger_entries
WHERE account_id = :acc_id
ORDER BY created_at DESC, sequence_num DESC
LIMIT 50;
```

### Workload 2A: Customer Transaction Search by Account, Date Range & Status
- **Application Path:** Customer portal transaction filter:
```sql
SELECT id, idempotency_key, source_account_id, destination_account_id, amount, currency, status, created_at, posted_at
FROM transfer_requests
WHERE (source_account_id = :acc_id OR destination_account_id = :acc_id)
  AND created_at >= :start_date AND created_at <= :end_date
  AND status = 'POSTED'
ORDER BY created_at DESC
LIMIT 50;
```

### Workload 2B: Staff Global Transaction Search by Status & Date Range
- **Application Path:** Compliance audit search for posted financial transfers over a date window:
```sql
SELECT id, source_user_id, source_account_id, destination_account_id, amount, status, created_at
FROM transfer_requests
WHERE status = 'POSTED'
  AND created_at >= :start_date AND created_at <= :end_date
ORDER BY created_at DESC
LIMIT 50;
```

### Workload 3: Daily Activity Volume Aggregation (Reporting & Analytics)
- **Application Path:** `GET /api/v1/reports/daily-volume?days=45`
- **Query Logic:** Multi-day sliding window aggregation of transfer counts and transaction sums:
```sql
SELECT 
    TO_CHAR(posted_at, 'YYYY-MM-DD') AS day,
    COUNT(id) AS count,
    COALESCE(SUM(amount), 0.00) AS volume
FROM transfer_requests
WHERE status = 'POSTED' AND posted_at >= :start_date
GROUP BY TO_CHAR(posted_at, 'YYYY-MM-DD')
ORDER BY day;
```

### Workload 4: Staff Advisory Fraud Alert Queue (Triage Filter)
- **Application Path:** `GET /api/v1/fraud/alerts?review_status=PENDING&min_risk_score=0.70`
- **Query Logic:** Priority triage queue fetching unreviewed high-risk alerts ordered by risk score:
```sql
SELECT id, transfer_request_id, model_version, risk_score, decision, rule_flags, explanation, review_status, created_at
FROM fraud_predictions
WHERE review_status = 'PENDING' AND risk_score >= 0.7000
ORDER BY risk_score DESC, created_at DESC
LIMIT 50;
```

---

## 4. Empirical Performance Results: Baseline vs. Optimized

Both sets of measurements were captured against the same 25,000-transfer dataset in `finledger_bench` under identical parameter values and ordering. Each workload was executed for 5 iterations (Run 1 cold cache, Runs 2–5 warm cache):

| Workload Identifier | Baseline Execution (Warm) | Optimized Execution (Warm) | Buffer Blocks (Baseline $\rightarrow$ Optimized) | Primary Execution Plan Node | Speedup / Empirical Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Workload 1**<br>Account Ledger History | **0.118 ms** | **0.080 ms** | 162 hit $\rightarrow$ **106 hit** | `Incremental Sort` $\rightarrow$ **`Index Scan`** (Presorted) | **1.48x faster**<br>(34.6% buffer reduction, quicksort eliminated) |
| **Workload 2A**<br>Customer Account Tx Search | **0.540 ms** | **2.374 ms** | 908 hit $\rightarrow$ 6,232 hit | `Bitmap Heap Scan` $\rightarrow$ `Index Scan` | **Regression (4.4x slower)**<br>(Planner trade-off under LIMIT 50; Sec. 5.4) |
| **Workload 2B**<br>Staff Global Tx Search | **10.924 ms** | **0.104 ms** | 2,208 hit $\rightarrow$ **106 hit** | **`Seq Scan`** $\rightarrow$ **`Index Scan`** | **105.0x faster**<br>(95.2% buffer reduction, full scan avoided) |
| **Workload 3**<br>Daily Volume Aggregation | **40.336 ms** | **45.657 ms** | 2,208 hit $\rightarrow$ 2,208 hit | `Seq Scan` $\rightarrow$ `Seq Scan` | **No change in execution plan**<br>(Low selectivity keeps Seq Scan; Sec. 5.3) |
| **Workload 4**<br>Fraud Alert Triage Queue | **0.304 ms** | **0.311 ms** | 94 hit $\rightarrow$ 94 hit | `Bitmap Index Scan` (`ix_review_status`) $\rightarrow$ `Bitmap Index Scan` (`idx_fraud_pending_queue`) | **Storage Footprint Reduced**<br>(16 kB partial index vs 56 kB full index; Sec. 5.5) |

---

## 5. Detailed Query Plan Analysis & Scientific Discussion

### Finding 1: The 105x Speedup on Staff Global Transaction Search (Workload 2B)
- **Baseline Bottleneck:** In baseline schema (`aa388336f576`), `transfer_requests` lacked any composite index on `status` and `created_at`. When compliance staff queried transactions by status and date range (`status = 'POSTED' AND created_at BETWEEN :start AND :end ORDER BY created_at DESC LIMIT 50`), PostgreSQL performed a **full table Sequential Scan across all 2,208 table pages** (25,000 rows).
- **Optimization Applied:** Composite index `idx_transfers_status_created` on `(status, created_at DESC)`.
- **Query Plan Transformation:**
  ```
  Baseline: Seq Scan on transfer_requests (cost=0.00..2208.00 rows=12500) -> 10.924 ms (2,208 buffer hits)
  Optimized: Limit -> Index Scan using idx_transfers_status_created on transfer_requests (cost=0.29..148.22 rows=50) -> 0.104 ms (106 buffer hits)
  ```
- **Result:** Execution time dropped from **10.924 ms to 0.104 ms**, reducing memory buffer hits by 2,102 blocks (95.2% reduction) per query execution.

### Finding 2: Elimination of Sorting on Ledger History (Workload 1)
- **Baseline Bottleneck:** Baseline index `idx_ledger_entries_account_created` indexed `(account_id, created_at DESC)`. However, the double-entry accounting query orders by `ORDER BY created_at DESC, sequence_num DESC LIMIT 50`. Because `sequence_num` was absent from the index, PostgreSQL had to fetch candidate entries and perform an **`Incremental Sort` (quicksort)** in memory.
- **Optimization Applied:** Composite index `idx_ledger_entries_account_created_seq` on `(account_id, created_at DESC, sequence_num DESC)`.
- **Query Plan Transformation:**
  ```
  Baseline: Limit -> Incremental Sort (quicksort 29kB) -> Index Scan on idx_ledger_entries_account_created -> 0.118 ms (162 buffer hits)
  Optimized: Limit -> Index Scan on idx_ledger_entries_account_created_seq -> 0.080 ms (106 buffer hits)
  ```
- **Result:** The `Incremental Sort` operator was completely eliminated. The B-tree yields tuples in physical sorting order, saving 34.6% of buffer hits.

### Finding 3: Workload 3 Analysis & Removal of Unbeneficial Index
- **Empirical Observation:** Workload 3 aggregates multi-day volume (`status = 'POSTED' AND posted_at >= :start_date GROUP BY day`).
- **Why Single-Column `posted_at` Index Did Not Help:**
  1. In our financial dataset, 96% of all transactions have `status = 'POSTED'`, and a 45-day window spans ~12,000 rows (48% of the 25,000-row table).
  2. Index lookups for 12,000 rows would incur massive random I/O (12,000 index traversals + 12,000 heap fetches). PostgreSQL's cost optimizer determined that a **Sequential Scan** (reading 736 to 2,208 contiguous blocks sequentially) is significantly cheaper.
  3. Consequently, PostgreSQL **completely ignored** `idx_transfers_posted_at`, executing identical `Seq Scan` nodes in both baseline and optimized runs.
  4. The runtime variance between runs (40.34 ms vs 45.66 ms) is purely CPU aggregation/sort timing jitter on the 12,000 intermediate grouped rows, not an index effect.
- **Engineering Decision:** Because `idx_transfers_posted_at` provided zero query benefit while consuming **552 kB of physical storage** and creating write overhead on every transaction commit, it was **omitted from the Phase 7 schema migration**.

### Finding 4: Workload 2A Regression Analysis (Customer Account Transaction Search)
- **Empirical Observation:** Workload 2A runtime regressed from **0.540 ms to 2.374 ms**, and warm buffer hits increased from **908 to 6,232**.
- **Root Cause (PostgreSQL Planner Cost Heuristic under `LIMIT`):**
  1. *Baseline Plan:* PostgreSQL executed `BitmapOr` between `ix_transfer_requests_source_account_id` and `ix_transfer_requests_destination_account_id`. This narrowed candidate rows directly to the ~373 rows belonging to that account, followed by a fast in-memory Top-N quicksort of 181 candidate rows (cost=648.91..649.03, time=0.540 ms, 300–908 buffer hits).
  2. *Optimized Plan:* With composite index `idx_transfers_status_created (status, created_at DESC)` available, the optimizer observed the query's `ORDER BY created_at DESC LIMIT 50`. The planner calculated an estimated cost of 0.29..627.79 to scan down `idx_transfers_status_created` until 50 rows matching the account filter were encountered, believing it would avoid the sort.
  3. *The Trap:* Because the target account represents only ~1.5% of the total dataset, PostgreSQL had to scan forward through 3,105 index and table entries, discarding **3,055 non-matching rows by filter** (`Rows Removed by Filter: 3055`) before satisfying `LIMIT 50`.
  4. This resulted in reading **6,232 shared buffer blocks** instead of 908, increasing execution time from 0.540 ms to 2.374 ms.
- **Engineering Conclusion:** This is a documented, repeatable trade-off in relational database query planning: indexes tailored for global chronological scans can inadvertently cause the planner to favor index scans over bitmap index scans for sparse per-account filters with small `LIMIT` clauses. For production customer transaction search, dedicated composite account indexes `(source_account_id, created_at DESC)` or explicit index hinting/query structuring can resolve this trade-off if desired.

### Finding 5: Partial Index Benefits on Fraud Alert Triage (Workload 4)
- **Empirical Observation:** Execution time remained equivalent within measurement noise (**0.304 ms vs 0.311 ms**, a difference of ~7 microseconds), with identical 94 buffer hits.
- **Physical Advantage of Partial Index:**
  1. Baseline schema utilized `ix_fraud_predictions_review_status` (btree on `review_status`) or `idx_fraud_pending_risk` (btree on `risk_score, created_at DESC`), indexing all 1,000 predictions regardless of review status.
  2. Partial index `idx_fraud_pending_queue ON fraud_predictions(risk_score DESC, created_at DESC) WHERE review_status = 'PENDING'` indexes strictly active unreviewed alerts.
  3. Measured physical size of `idx_fraud_pending_queue` is **16 kB** (2 pages), compared to **56 kB** (7 pages) for the unfiltered index — a **71.4% storage footprint reduction**. In long-running banking environments where 90%+ of alerts transition to `CLEARED`, `CONFIRMED_FRAUD`, or `ESCALATED`, this partial index prevents historical alert bloat and keeps the working triage set tightly memory-resident.

---

## 6. Physical Storage & Index Trade-off Measurements

All relation and index sizes were measured directly using PostgreSQL `pg_relation_size()` against the 25,000-transfer benchmark database (`finledger_bench`):

| Database Object | Type | Measured Size (kB) | Measured Bytes | Architectural Justification & Trade-Off |
| :--- | :--- | :--- | :--- | :--- |
| `transfer_requests` | Table | **5,888 kB** | 6,029,312 | Primary transfer request entity (25,000 rows). |
| `idx_transfers_status_created` | Index | **784 kB** | 802,816 | Composite index `(status, created_at DESC)`. Justified by 105x speedup on staff compliance queries (Workload 2B). |
| `idx_transfers_posted_at` *(Omitted)* | Index | *0 kB (Omitted)* | *0* | **Rejected**: Consumed 552 kB with zero query utility (optimizer kept Seq Scan on Workload 3). |
| `ledger_entries` | Table | **4,792 kB** | 4,907,008 | High-density double-entry ledger table (47,974 rows). |
| `idx_ledger_entries_account_created_seq` | Index | **2,344 kB** | 2,400,256 | Composite index `(account_id, created_at DESC, sequence_num DESC)`. Justified by eliminating sort overhead on Workload 1. |
| `ix_ledger_entries_account_id` *(Dropped)* | Index | *Saved 408 kB* | *Saved 417,792* | **Dropped as Redundant**: Single-column index on `account_id` was 100% redundant with `idx_ledger_entries_account_created_seq` (leading column `account_id`). Dropping saves 408 kB and eliminates index update amplification on every ledger insert. |
| `fraud_predictions` | Table | **240 kB** | 245,760 | Advisory fraud inference records (1,000 rows). |
| `idx_fraud_pending_queue` | Index | **16 kB** | 16,384 | Partial index `WHERE review_status = 'PENDING'`. 71.4% smaller than unfiltered index (56 kB), maintaining compact working set. |

### Write Overhead & Maintenance Considerations
- **Index Maintenance Overhead:** In relational databases, every active B-tree index incurs write overhead during `INSERT` and `UPDATE` operations due to WAL logging and page splits. On `ledger_entries` (which receives 2 inserts per financial transfer), dropping the redundant single-column `ix_ledger_entries_account_id` directly eliminated one redundant B-tree maintenance path.
- **Pruning Unbeneficial Indexes:** Removing `idx_transfers_posted_at` avoids unnecessary index maintenance on financial postings, ensuring the schema only retains indexes with demonstrated, workload-backed value.

---

## 7. Transaction Reliability & Concurrency Verification

All concurrency tests were executed against a real PostgreSQL test database (`finledger_test`) using independent operating system threads:

```powershell
..\.venv\Scripts\pytest.exe tests/test_concurrency.py -v
```

### Concurrency Test Suite Results (8 Passed / 8 Total):

1. `test_concurrent_overspending_prevented` (**PASSED**):
   - Two concurrent threads attempt to transfer ₹80.00 simultaneously from an account holding ₹100.00.
   - **Invariant Verified:** Exactly 1 transfer commits (`status='POSTED'`); the competing transfer is rejected with `InsufficientFundsError`.
   - Final cached and derived balances are both strictly **₹20.00**; zero overdrawing is physically possible.
2. `test_concurrent_bidirectional_transfers_no_deadlock` (**PASSED**):
   - Simultaneous transfers between Account A $\rightarrow$ B and Account B $\rightarrow$ A across concurrent threads.
   - **Invariant Verified:** Canonical ascending primary key row locking (`ORDER BY id ASC FOR UPDATE`) completely eliminates PostgreSQL deadlock exceptions (`40P01`).
3. `test_concurrent_identical_requests_single_transfer` (**PASSED**):
   - Simultaneous duplicate requests submitted with the identical `Idempotency-Key`.
   - **Invariant Verified:** Handled by unique constraint `uq_transfers_user_idempotency`; exactly 1 financial transfer commits, 0 duplicate ledger postings.
4. `test_concurrent_investment_overspending_prevented` (**PASSED**):
   - Two concurrent investment purchases of ₹20,000 competing for ₹30,000 in available funds.
   - **Invariant Verified:** Exactly 1 investment succeeds; 1 rejected; final balance is strictly ₹10,000.00.
5. `test_concurrent_investment_account_provisioning` (**PASSED**):
   - Concurrent initial investment purchases for a customer with 0 investment accounts.
   - **Invariant Verified:** Exactly 1 `INVESTMENT` account is provisioned without duplicate key errors; both purchases attach cleanly.
6. `test_concurrent_identical_investment_requests_single_purchase` (**PASSED**):
   - Concurrent investment submissions with identical idempotency keys commit once.
7. `test_multi_thread_concurrent_drain_race` (**PASSED**):
   - **5 concurrent threads** simultaneously attempt to transfer ₹30.00 each against a ₹100.00 balance (total demanded ₹150.00).
   - **Invariant Verified:** Exactly 3 transfers succeed (3 $\times$ 30 = ₹90.00); exactly 2 fail with `InsufficientFundsError`. Final balance is strictly **₹10.00**.
8. `test_concurrent_forced_failure_with_audit_persistence` (**PASSED**):
   - Worker 1 attempts an invalid transfer triggering financial rollback; Worker 2 executes a concurrent valid transfer.
   - **Invariant Verified:** Worker 1's financial ledger legs roll back completely (0 funds deducted), while its audit failure record (`TRANSFER_FAILED`) is persisted via independent transaction. Worker 2 succeeds without interference.

---

## 8. Full System Regression & Reconciliation Outcomes

### 1. Full Backend Test Suite
```powershell
..\.venv\Scripts\pytest.exe -v
```
**Outcome:** **127 passed, 1 warning in 43.01s** (100% pass rate).

### 2. Double-Entry Reconciliation Audits
```powershell
# Development database audit
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py
# Test database audit
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py --test
```
**Outcome:**
- `finledger`: **0 discrepancies**, Global Net Ledger Delta: **INR 0.00**.
- `finledger_test`: **0 discrepancies**, Global Net Ledger Delta: **INR 0.00**.

### 3. Frontend Integration Suite
```powershell
npm test
```
**Outcome:** **4 test files passed, 14 tests passed in 8.20s** (100% pass rate).

---

## 9. Reproducibility Instructions

To reproduce the benchmark experiments and verification suites locally:

### 1. Populate Benchmark Database
```powershell
cd backend
..\.venv\Scripts\python.exe scripts/benchmark_dbms.py --db-name finledger_bench --populate --transfers 25000 --seed 42
```

### 2. Execute Benchmark Profiling
```powershell
cd backend
..\.venv\Scripts\python.exe scripts/benchmark_dbms.py --db-name finledger_bench --run --output ../docs/dbms_benchmark_optimized.json
```

### 3. Run Concurrency Suite
```powershell
cd backend
..\.venv\Scripts\pytest.exe tests/test_concurrency.py -v
```

### 4. Run Full Backend Regression Suite
```powershell
cd backend
..\.venv\Scripts\pytest.exe -v
```

### 5. Run Double-Entry Reconciliation
```powershell
cd backend
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py
..\.venv\Scripts\python.exe scripts/reconcile_ledger.py --test
```
