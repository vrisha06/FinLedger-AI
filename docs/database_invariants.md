# FinLedger-AI — Database Invariants & Financial Integrity Rules

**Document:** Financial & Relational Invariants Specification  
**Status:** Approved  
**Related Documents:** [implementation_plan.md](file:///c:/Users/Saksham%20Raj/Downloads/bin/Game,Project/Projects/FinLedger-AI/docs/implementation_plan.md), [architecture.md](file:///c:/Users/Saksham%20Raj/Downloads/bin/Game,Project/Projects/FinLedger-AI/docs/architecture.md)

---

## 1. Overview of Financial Invariants

In financial transaction systems, database correctness is paramount. Application-level validations can fail, threads can race, and servers can crash mid-flight. To guarantee absolute consistency, **FinLedger-AI** enforces strict financial invariants at the relational database layer through normalization, constraints, transaction isolation, pessimistic locking, and database triggers.

---

## 2. Representation of Money

1. **Relational Representation**:
   - All monetary amounts, balances, and ledger entry legs are strictly defined as `NUMERIC(15, 2)` in PostgreSQL.
   - Floating-point types (`REAL`, `FLOAT`, `DOUBLE PRECISION`) are **strictly prohibited** in financial tables.
2. **Application Representation**:
   - All monetary fields in Python and FastAPI are represented using Python's standard `decimal.Decimal` class.
   - Rounding mode is explicitly set to `ROUND_HALF_EVEN` (Banker's Rounding) for calculations.
3. **Currency Invariant**:
   - All accounts, transfers, and ledger entries are denominated in **Indian Rupee (INR)**.
   - Single-currency enforcement is verified by database check constraint: `CHECK (currency = 'INR')`.

---

## 3. Double-Entry Ledger Accounting Convention

FinLedger-AI implements traditional double-entry bookkeeping using the banking ledger convention:

### 3.1 Account Classifications
- **Customer Accounts (Savings & Current)**:
  - Classified as **Liabilities** from the bank's operational viewpoint (money the bank owes to its depositors).
  - A **Credit** entry increases the bank's liability to the customer $\to$ **increases customer account balance**.
  - A **Debit** entry decreases the bank's liability to the customer $\to$ **decreases customer account balance**.
- **Internal System Accounts (Clearing & Reserves)**:
  - Account Number: `INR-SYS-CLEARING`.
  - Classified as **Assets / Clearing Reserves**.
  - Used as the offsetting leg for external money injections (e.g., initial deposits, opening funds).

### 3.2 Customer-to-Customer Transfer Posting
When Customer A transfers ₹1,000.00 to Customer B:
$$\begin{array}{|l|l|c|r|}
\hline
\textbf{Account} & \textbf{Entry Type} & \textbf{Amount (INR)} & \textbf{Effect on Balance} \\
\hline
\text{Customer A Account (Source)} & \text{DEBIT} & 1,000.00 & \text{Decreases by 1,000.00} \\
\text{Customer B Account (Destination)} & \text{CREDIT} & 1,000.00 & \text{Increases by 1,000.00} \\
\hline
\end{array}$$
$$\sum \text{Debits} (1,000.00) = \sum \text{Credits} (1,000.00) \implies \Delta \text{Net} = 0.00$$

### 3.3 Opening Deposit / Capital Injection
Money is **never** created by directly editing an account balance. To fund an account with ₹50,000.00:
$$\begin{array}{|l|l|c|r|}
\hline
\textbf{Account} & \textbf{Entry Type} & \textbf{Amount (INR)} & \textbf{Effect on Balance} \\
\hline
\text{INR-SYS-CLEARING (Internal)} & \text{DEBIT} & 50,000.00 & \text{Clearing Asset debited} \\
\text{Customer Account} & \text{CREDIT} & 50,000.00 & \text{Customer balance increases} \\
\hline
\end{array}$$
$$\sum \text{Debits} (50,000.00) = \sum \text{Credits} (50,000.00)$$

---

## 4. Multi-Row Balanced Posting Validation

### The Relational Problem
Standard SQL `CHECK` constraints are row-level; they cannot execute subqueries or compute aggregates across multiple rows in a table. Because a double-entry transaction consists of multiple separate rows in `ledger_entries`, a basic `CHECK` constraint cannot verify that the debits match the credits for the parent `transaction_id`.

### The Solution: Deferrable Constraint Triggers
FinLedger-AI implements a PostgreSQL `CONSTRAINT TRIGGER` declared as `DEFERRABLE INITIALLY DEFERRED`. This trigger fires at transaction `COMMIT` time, evaluating the entire transaction set:

```sql
CREATE OR REPLACE FUNCTION verify_transaction_balance()
RETURNS TRIGGER AS $$
DECLARE
    balance_diff NUMERIC(15, 2);
BEGIN
    SELECT COALESCE(SUM(CASE WHEN entry_type = 'DEBIT' THEN amount ELSE -amount END), 0)
    INTO balance_diff
    FROM ledger_entries
    WHERE transaction_id = NEW.transaction_id;

    IF balance_diff <> 0 THEN
        RAISE EXCEPTION 'Ledger transaction % is unbalanced: debit minus credit delta is %',
            NEW.transaction_id, balance_diff
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_verify_ledger_balance
AFTER INSERT OR UPDATE ON ledger_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION verify_transaction_balance();
```

If any software bug, service crash, or ad-hoc query attempts to insert an unbalanced transaction leg, PostgreSQL rejects the commit and aborts the entire transaction.

---

## 5. Account-Balance Strategy & Atomic Caching

### 5.1 Source of Truth
The canonical source of truth for any account balance is the mathematical sum of its immutable ledger postings:
$$\text{Derived Balance} = \sum_{e \in \text{CREDIT}} e.amount - \sum_{e \in \text{DEBIT}} e.amount$$

### 5.2 Atomic Cached Balance
To avoid executing an aggregate `SUM()` query across millions of historical ledger entries on every balance check or transfer, `accounts.cached_balance` stores the current balance.
- **Atomic Modification Rule**: The `cached_balance` field is **only** modified inside the exact same database transaction that inserts the matching `ledger_entries`.
- **Non-Negative Balance Constraint**: Customer accounts must never be overdrawn:
  ```sql
  ALTER TABLE accounts ADD CONSTRAINT chk_customer_non_negative_balance
  CHECK (account_type = 'INTERNAL_CLEARING' OR cached_balance >= 0.00);
  ```

### 5.3 Balance Reconciliation Engine
A system-wide reconciliation audit compares `cached_balance` against the derived ledger sum for every account:
```sql
SELECT a.id, a.account_number, a.cached_balance,
       COALESCE(SUM(CASE WHEN le.entry_type = 'CREDIT' THEN le.amount ELSE -le.amount END), 0) AS derived_balance,
       (a.cached_balance - COALESCE(SUM(CASE WHEN le.entry_type = 'CREDIT' THEN le.amount ELSE -le.amount END), 0)) AS discrepancy
FROM accounts a
LEFT JOIN ledger_entries le ON a.id = le.account_id
GROUP BY a.id, a.account_number, a.cached_balance
HAVING a.cached_balance <> COALESCE(SUM(CASE WHEN le.entry_type = 'CREDIT' THEN le.amount ELSE -le.amount END), 0);
```
In an automated verification test, this query must return exactly 0 rows.

---

## 6. Concurrency Control & Canonical Row Locking

### 6.1 The Deadlock Problem
In high-throughput environments, bi-directional transfers can cause deadlocks:
- Transaction 1: Transfers from Account A $\to$ Account B (Locks A, then waits for B).
- Transaction 2: Transfers from Account B $\to$ Account A (Locks B, then waits for A).
- Result: PostgreSQL detects a deadlock and forcibly aborts one of the transactions.

### 6.2 Deadlock Prevention via Canonical Ordering
FinLedger-AI completely eliminates deadlock graphs by enforcing a deterministic lock-acquisition order across all transactions:
1. Sort the primary keys of the source and destination accounts:
   $$\text{lock\_first} = \min(\text{source\_id}, \text{dest\_id}), \quad \text{lock\_second} = \max(\text{source\_id}, \text{dest\_id})$$
2. Acquire pessimistic row locks using `SELECT ... FOR UPDATE`:
   ```sql
   SELECT id, cached_balance, status, customer_id
   FROM accounts
   WHERE id IN (:lock_first, :lock_second)
   ORDER BY id ASC
   FOR UPDATE;
   ```
Because every transaction locks accounts in ascending order, circular wait conditions cannot occur.

### 6.3 Double-Spending Prevention
When multiple concurrent requests attempt to withdraw funds from the same account:
1. The first transaction acquires the `FOR UPDATE` lock on the source account.
2. Subsequent concurrent transactions block waiting for the lock.
3. The first transaction checks available funds, deducts the amount, inserts ledger entries, and commits.
4. The waiting transaction unblocks and reads the freshly committed balance.
5. If the remaining balance is insufficient, it raises `InsufficientFundsError` and cleanly rolls back.
No overdraft or lost update is possible under this protocol.

---

## 7. Scoped Idempotency Invariants

To safeguard against network timeouts, client double-clicks, and automated retries:
1. **Idempotency Scope**:
   - Enforced by unique constraint: `UNIQUE (source_user_id, idempotency_key)`.
   - Keys are scoped per authenticated customer; different customers may safely generate identical UUIDs without conflict.
2. **Payload Fingerprint Verification**:
   - The SHA-256 hash of the canonical request payload is stored alongside the key:
     $$\text{request\_hash} = \text{SHA256}(\text{source\_id} \,\|\, \text{dest\_id} \,\|\, \text{amount} \,\|\, \text{currency} \,\|\, \text{memo})$$
3. **Execution Semantics**:
   - **Identical Replay**: If the key exists with the **identical** payload hash, the server returns the cached result without executing a second debit (`200 OK` or `201 Created`).
   - **Key Collision / Tampering**: If the key exists with a **different** payload hash, the server rejects the request with `409 Conflict`.

---

## 8. Ledger & Audit Immutability Invariants

1. **No Application Updates or Deletions**:
   - Application APIs provide zero endpoints for updating or deleting `ledger_entries` or `audit_logs`.
2. **Database-Enforced Immutability Triggers**:
   - PostgreSQL triggers prevent any direct SQL `UPDATE` or `DELETE` statements on historical entries:
     ```sql
     CREATE OR REPLACE FUNCTION prevent_modification()
     RETURNS TRIGGER AS $$
     BEGIN
         RAISE EXCEPTION 'Table % is strictly append-only; updates and deletes are prohibited', TG_TABLE_NAME
             USING ERRCODE = 'restrict_violation';
     END;
     $$ LANGUAGE plpgsql;

     CREATE TRIGGER trg_immutable_ledger_entries
     BEFORE UPDATE OR DELETE ON ledger_entries
     FOR EACH ROW EXECUTE FUNCTION prevent_modification();

     CREATE TRIGGER trg_immutable_audit_logs
     BEFORE UPDATE OR DELETE ON audit_logs
     FOR EACH ROW EXECUTE FUNCTION prevent_modification();
     ```
3. **Reversal Transactions**:
   - If a transfer was recorded incorrectly, it must be corrected by creating a new `CORRECTION_REVERSAL` transaction with inverted debit and credit legs. Both the original postings and the reversal postings remain in the ledger forever.

---

## 9. Transaction Atomicity, Rollback & Independent Audit Persistence

### 9.1 Financial Unit of Work Atomicity
Every posted financial transfer must execute as an atomic unit of work within a dedicated financial database transaction (`financial_txn`):
$$\text{LedgerTransaction} \land \text{LedgerEntry}_{\text{debit}} \land \text{LedgerEntry}_{\text{credit}} \land \Delta\text{Balance}_{\text{src}} \land \Delta\text{Balance}_{\text{dst}}$$
If an exception occurs at any point before commit (e.g., insufficient funds, inactive account, database trigger violation, or unhandled server crash):
- The `financial_txn` is immediately and completely **ROLLED BACK**.
- Zero partial debit or credit postings are committed to PostgreSQL.
- Account balances remain completely unchanged.

### 9.2 Independent Transaction Architecture for Failed Transfers & Audit Logs
In financial systems, an audit trail must be tamper-evident and complete. If audit records or failed transfer records were written within the same database transaction as the financial ledger, rolling back the financial transaction would **accidentally erase the required audit evidence and record of the failed transfer attempt**.

To prevent this critical failure mode, FinLedger-AI implements a **Two-Phase / Independent Transaction Architecture**:

1. **Isolation of Financial Execution (`financial_txn`)**:
   - Acquires pessimistic locks on accounts, validates funds, and attempts to post double-entry ledger entries.
   - If validation fails (e.g., `InsufficientFundsError`, `InvalidAccountError`) or a database error occurs, `financial_txn` is explicitly rolled back.
2. **Dedicated Audit & Failure Persistence (`audit_txn`)**:
   - The failure event is handled in an independent database transaction context:
     - The `transfer_requests` row is persisted with `status = 'FAILED'`, `failure_reason = <sanitized_reason>`, and `posted_at = NULL`.
     - An `audit_logs` entry is persisted with `action = 'TRANSFER_FAILED'`, `actor_user_id`, `entity_type = 'TRANSFER'`, `entity_id`, client IP address, and sanitized metadata (e.g., attempted amount, source account ID, failure classification).
   - This `audit_txn` is committed independently.
3. **Audit Trail Preservation Guarantees**:
   - Failed financial transactions **never erase audit evidence**. Forensic investigators and staff can inspect every failed attempt, identifying brute-force attempts, automated balance-probing attacks, or systemic payment gateway issues.
   - Plaintext passwords, secrets, or JWT tokens are strictly excluded from the audit payload.
4. **Idempotency Under Failure**:
   - Because the failed attempt is committed to `transfer_requests` with `(source_user_id, idempotency_key)` and `status = 'FAILED'`, any subsequent retry by the client with the identical key will query this record and immediately return the original cached error response, preventing redundant recalculations or race conditions. Reusing the key with altered parameters returns `409 Conflict`.

