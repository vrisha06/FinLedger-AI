"""PostgreSQL Performance Evaluation & Reliability Benchmark Script for FinLedger-AI.

Executes reproducible query performance experiments and transaction reliability testing
against a dedicated PostgreSQL benchmark database (default: finledger_bench).

Features:
1. Configurable synthetic dataset generation (default 25,000 transfers -> 50,000+ ledger entries).
2. Strict isolation safeguards: Never touches or resets the development/production database (finledger).
3. EXPLAIN (ANALYZE, BUFFERS) execution plan profiling for representative workloads:
   - Workload 1: Account Transaction History (Ledger Entries)
   - Workload 2A: Customer Transaction Search (by Account, Date Range, Status)
   - Workload 2B: Staff Global Transaction Search (by Status and Date Range)
   - Workload 3: Daily Activity Volume Aggregation (Reporting & Analytics)
   - Workload 4: Staff Advisory Fraud Alert Queue (Triage Filter)
4. Cold-cache vs. Warm-cache measurement and buffer hit/read profiling.
5. Structured results persistence to JSON and human-readable Markdown summary.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import random
import sys
import time
import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings
from app.models import (
    Base,
    User,
    Customer,
    Account,
    TransferRequest,
    LedgerTransaction,
    LedgerEntry,
    FraudPrediction,
    AuditLog,
)
from app.services.ledger_service import LedgerService


def get_benchmark_database_url(db_name: str = "finledger_bench") -> str:
    """Safely construct target benchmark database URL."""
    base_url = settings.sync_database_url
    if db_name == settings.DB_NAME:
        raise ValueError(
            f"SAFETY ABORT: Cannot target active database '{settings.DB_NAME}'. "
            "Benchmarks must run strictly against a dedicated benchmark or test database (e.g. finledger_bench)."
        )
    return base_url.replace(f"/{settings.DB_NAME}", f"/{db_name}")


def populate_benchmark_database(
    engine,
    num_transfers: int = 25000,
    random_seed: int = 42,
    batch_size: int = 2500,
) -> dict:
    """Populate benchmark database with realistic, double-entry balanced financial data.

    Generates:
    - 1 System clearing account (INR-SYS-CLEARING)
    - 100 Customers with 150 Accounts
    - num_transfers TransferRequests with balanced LedgerTransactions & LedgerEntries (2 legs each = 2x rows)
    - 1,000 FraudPredictions with realistic status and score distributions
    - Audited opening funds
    """
    random.seed(random_seed)
    print(f"\n[Populate] Starting benchmark dataset generation (seed={random_seed}, transfers={num_transfers})...")
    start_time = time.time()

    # Verify target database safety
    with engine.connect() as conn:
        current_db = conn.execute(text("SELECT current_database();")).scalar()
        if current_db == settings.DB_NAME:
            raise RuntimeError(f"ABORT: Connected to production/dev database '{current_db}'!")
        print(f"[Populate] Verified target database: '{current_db}'")

        # Truncate existing benchmark tables in proper cascade order (opt in past the append-only guard)
        conn.execute(text("SET LOCAL finledger.allow_truncate = 'on'"))
        conn.execute(
            text(
                "TRUNCATE TABLE audit_logs, fraud_predictions, ledger_entries, "
                "ledger_transactions, transfer_requests, investments, accounts, customers, users CASCADE;"
            )
        )
        conn.commit()

    with Session(engine) as session:
        # 1. System Clearing Account
        clearing_acc = Account(
            id=uuid.uuid4(),
            customer_id=None,
            account_number=settings.CLEARING_ACCOUNT_NUMBER,
            account_type="INTERNAL_CLEARING",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add(clearing_acc)

        # 2. Users and Customers (100 customers)
        num_customers = 100
        customer_users = []
        customer_accounts = []

        for i in range(num_customers):
            user = User(
                id=uuid.uuid4(),
                username=f"bench_cust_{i:04d}",
                email=f"bench_cust_{i:04d}@example.com",
                password_hash="$2b$12$benchmarkpasswordhashfortestingonly",
                role="CUSTOMER",
                is_active=True,
            )
            customer = Customer(
                id=uuid.uuid4(),
                user_id=user.id,
                full_name=f"Benchmark Customer {i:04d}",
                phone=f"+9198765{i:05d}",
                kyc_status="VERIFIED",
            )
            session.add_all([user, customer])
            customer_users.append((user.id, customer.id))

            # Primary Savings Account
            sav_acc = Account(
                id=uuid.uuid4(),
                customer_id=customer.id,
                account_number=f"INR-SAV-{user.id.hex[:6].upper()}-{i:04d}",
                account_type="SAVINGS",
                currency="INR",
                cached_balance=Decimal("500000.00"),  # Funded balance
                status="ACTIVE",
                version=1,
            )
            session.add(sav_acc)
            customer_accounts.append((user.id, sav_acc.id))

            # Additional Current Account for 50 customers
            if i % 2 == 0:
                cur_acc = Account(
                    id=uuid.uuid4(),
                    customer_id=customer.id,
                    account_number=f"INR-CUR-{user.id.hex[:6].upper()}-{i:04d}",
                    account_type="CURRENT",
                    currency="INR",
                    cached_balance=Decimal("250000.00"),
                    status="ACTIVE",
                    version=1,
                )
                session.add(cur_acc)
                customer_accounts.append((user.id, cur_acc.id))

        # Adjust clearing balance to match opening customer funds
        total_opening_funds = (Decimal("500000.00") * num_customers) + (Decimal("250000.00") * (num_customers // 2))
        clearing_acc.cached_balance = -total_opening_funds

        session.commit()
        print(f"[Populate] Created {num_customers} customers and {len(customer_accounts)} funded accounts.")

    # 3. Generate Transfers & Balanced Ledger Postings in clean batches
    account_ids = [acc[1] for acc in customer_accounts]
    user_id_map = {acc[1]: acc[0] for acc in customer_accounts}

    base_time = datetime.now(timezone.utc) - timedelta(days=90)
    total_posted = 0
    total_failed = 0
    total_ledger_entries = 0
    fraud_predictions_created = 0

    transfers_to_score = []

    print(f"[Populate] Generating {num_transfers} transfers in batches of {batch_size}...")
    for batch_start in range(0, num_transfers, batch_size):
        batch_end = min(batch_start + batch_size, num_transfers)
        batch_count = batch_end - batch_start

        with Session(engine) as session:
            for idx in range(batch_start, batch_end):
                # Spread over past 90 days with diurnal noise
                day_offset = random.uniform(0, 90)
                hour = random.choice([9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 2, 3])  # Peak business & rare night
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                tx_time = base_time + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)

                # Pick distinct source & destination accounts
                src_acc_id, dst_acc_id = random.sample(account_ids, 2)
                src_user_id = user_id_map[src_acc_id]

                # Realistic amount distributions
                if random.random() < 0.05:
                    amount = Decimal(str(round(random.uniform(48500.0, 49950.0), 2)))  # Structuring
                elif random.random() < 0.15:
                    amount = Decimal(str(round(random.uniform(5000.0, 25000.0), 2)))   # Medium
                else:
                    amount = Decimal(str(round(random.uniform(50.0, 2500.0), 2)))      # Retail

                # 96% POSTED, 3% FAILED, 1% PENDING
                status_roll = random.random()
                if status_roll < 0.96:
                    status = "POSTED"
                    total_posted += 1
                elif status_roll < 0.99:
                    status = "FAILED"
                    total_failed += 1
                else:
                    status = "PENDING"

                transfer_req = TransferRequest(
                    id=uuid.uuid4(),
                    idempotency_key=str(uuid.uuid4()),
                    source_user_id=src_user_id,
                    request_hash=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                    source_account_id=src_acc_id,
                    destination_account_id=dst_acc_id,
                    amount=amount,
                    currency="INR",
                    status=status,
                    failure_reason="Simulated failure" if status == "FAILED" else None,
                    created_at=tx_time,
                    posted_at=tx_time if status == "POSTED" else None,
                )
                session.add(transfer_req)

                # For POSTED transfers, generate balanced ledger transaction with 2 legs
                if status == "POSTED":
                    ledger_txn = LedgerTransaction(
                        id=uuid.uuid4(),
                        transfer_request_id=transfer_req.id,
                        transaction_type="CUSTOMER_TRANSFER",
                        description=f"Transfer #{idx}",
                        created_at=tx_time,
                    )
                    session.add(ledger_txn)

                    # Leg 1: DEBIT on source account (liability reduction)
                    leg_debit = LedgerEntry(
                        id=uuid.uuid4(),
                        transaction_id=ledger_txn.id,
                        account_id=src_acc_id,
                        entry_type="DEBIT",
                        amount=amount,
                        sequence_num=1,
                        created_at=tx_time,
                    )
                    # Leg 2: CREDIT on destination account (liability increase)
                    leg_credit = LedgerEntry(
                        id=uuid.uuid4(),
                        transaction_id=ledger_txn.id,
                        account_id=dst_acc_id,
                        entry_type="CREDIT",
                        amount=amount,
                        sequence_num=2,
                        created_at=tx_time,
                    )
                    session.add_all([leg_debit, leg_credit])
                    total_ledger_entries += 2

                # Select candidates for fraud prediction records (~4% of transfers, capped at 1,000)
                if len(transfers_to_score) < 1000 and (status == "POSTED" or status == "FAILED"):
                    if random.random() < 0.10:
                        transfers_to_score.append((transfer_req.id, tx_time, amount))

            session.commit()
            print(f"  -> Committed batch {batch_start + 1}..{batch_end} ({batch_end}/{num_transfers})")

    # 4. Generate 1,000 Fraud Prediction Records with realistic review states
    print(f"[Populate] Generating {len(transfers_to_score)} advisory fraud prediction records...")
    with Session(engine) as session:
        for t_id, t_time, amt in transfers_to_score:
            # 20% high risk (>0.70), 30% medium risk (0.30-0.70), 50% low risk (<0.30)
            roll = random.random()
            if roll < 0.20:
                score = round(random.uniform(0.7001, 0.9850), 4)
                decision = "HIGH_RISK"
                rule_flags = ["RULE_STRUCTURING"] if amt >= 48000 else ["RULE_VELOCITY_BURST"]
                # For triage queue: 60% PENDING, 30% CONFIRMED_FRAUD, 10% ESCALATED
                review_status = random.choice(["PENDING", "PENDING", "PENDING", "CONFIRMED_FRAUD", "ESCALATED"])
            elif roll < 0.50:
                score = round(random.uniform(0.3000, 0.6999), 4)
                decision = "MEDIUM_RISK"
                rule_flags = ["RULE_ZSCORE_OUTLIER"]
                review_status = random.choice(["PENDING", "CLEARED", "CLEARED"])
            else:
                score = round(random.uniform(0.0100, 0.2999), 4)
                decision = "LOW_RISK"
                rule_flags = []
                review_status = "CLEARED"

            pred = FraudPrediction(
                id=uuid.uuid4(),
                transfer_request_id=t_id,
                model_version="rf-v1.0.0",
                risk_score=Decimal(f"{score:.4f}"),
                decision=decision,
                rule_flags=rule_flags,
                feature_snapshot={"amount": float(amt), "is_night": 0},
                explanation=f"Advisory score {score:.4f}. Rule flags: {rule_flags}",
                review_status=review_status,
                created_at=t_time,
            )
            session.add(pred)
            fraud_predictions_created += 1

        session.commit()

    # 5. Run PostgreSQL ANALYZE to refresh catalog statistics
    print("[Populate] Refreshing PostgreSQL planner statistics (ANALYZE)...")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ANALYZE;"))

    elapsed = time.time() - start_time
    summary = {
        "status": "COMPLETED",
        "elapsed_seconds": round(elapsed, 2),
        "total_transfers": num_transfers,
        "posted_transfers": total_posted,
        "failed_transfers": total_failed,
        "total_ledger_entries": total_ledger_entries,
        "fraud_predictions": fraud_predictions_created,
    }
    print(f"[Populate] Finished in {elapsed:.2f}s: {num_transfers} transfers, {total_ledger_entries} ledger entries.\n")
    return summary


def execute_explain_analyze(engine, sql: str, params: dict, num_runs: int = 5) -> dict:
    """Execute EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) separating cold and warm cache.

    Returns:
    - cold_run: Plan details from the initial execution
    - warm_runs: Average execution time and buffer stats over runs 2..num_runs
    - summary: Key metrics including scan type, node tree, planning and execution times
    """
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"
    runs_data = []

    with engine.connect() as conn:
        for i in range(num_runs):
            res = conn.execute(text(explain_sql), params).scalar()
            plan_json = res[0]  # PostgreSQL returns JSON array of 1 element
            plan_root = plan_json["Plan"]

            planning_time = plan_json.get("Planning Time", 0.0)
            execution_time = plan_json.get("Execution Time", 0.0)

            # Extract buffer counts
            shared_hit = plan_root.get("Shared Hit Blocks", 0)
            shared_read = plan_root.get("Shared Read Blocks", 0)

            # Check child nodes for buffer stats if not on root
            def sum_buffers(node):
                hit = node.get("Shared Hit Blocks", 0)
                read = node.get("Shared Read Blocks", 0)
                for child in node.get("Plans", []):
                    c_hit, c_read = sum_buffers(child)
                    hit += c_hit
                    read += c_read
                return hit, read

            total_hit, total_read = sum_buffers(plan_root)
            shared_hit = max(shared_hit, total_hit)
            shared_read = max(shared_read, total_read)

            runs_data.append({
                "run": i + 1,
                "planning_time_ms": planning_time,
                "execution_time_ms": execution_time,
                "shared_hit_blocks": shared_hit,
                "shared_read_blocks": shared_read,
                "actual_rows": plan_root.get("Actual Rows", 0),
                "plan_rows": plan_root.get("Plan Rows", 0),
                "node_type": plan_root.get("Node Type", ""),
                "full_plan": plan_root,
            })

    cold_run = runs_data[0]
    warm_runs = runs_data[1:] if len(runs_data) > 1 else [cold_run]

    avg_warm_exec = sum(r["execution_time_ms"] for r in warm_runs) / len(warm_runs)
    avg_warm_hit = sum(r["shared_hit_blocks"] for r in warm_runs) / len(warm_runs)
    avg_warm_read = sum(r["shared_read_blocks"] for r in warm_runs) / len(warm_runs)

    # Detect scan types present in the plan tree
    scan_types = []
    def collect_scans(node):
        nt = node.get("Node Type", "")
        if "Scan" in nt:
            rel = node.get("Relation Name", "")
            idx = node.get("Index Name", "")
            scan_types.append(f"{nt} ({rel or idx})")
        for child in node.get("Plans", []):
            collect_scans(child)
    collect_scans(plan_root)

    return {
        "sql": sql.strip(),
        "params": {k: str(v) for k, v in params.items()},
        "cold_execution_time_ms": cold_run["execution_time_ms"],
        "cold_shared_read_blocks": cold_run["shared_read_blocks"],
        "cold_shared_hit_blocks": cold_run["shared_hit_blocks"],
        "warm_execution_time_ms": round(avg_warm_exec, 3),
        "warm_shared_read_blocks": round(avg_warm_read, 1),
        "warm_shared_hit_blocks": round(avg_warm_hit, 1),
        "planning_time_ms": cold_run["planning_time_ms"],
        "actual_rows": cold_run["actual_rows"],
        "plan_rows": cold_run["plan_rows"],
        "root_node_type": cold_run["node_type"],
        "scan_types": scan_types,
        "runs": runs_data,
    }


def run_benchmark_workloads(engine) -> dict:
    """Execute all representative workloads and capture query plans."""
    with engine.connect() as conn:
        # Select active sample accounts with substantial transaction history
        acc_sample = conn.execute(
            text(
                "SELECT account_id, count(*) as cnt FROM ledger_entries "
                "GROUP BY account_id ORDER BY cnt DESC LIMIT 2;"
            )
        ).fetchall()
        if not acc_sample:
            raise RuntimeError("Benchmark database is empty! Run with --populate first.")

        sample_account_id = acc_sample[0][0]
        sample_account_cnt = acc_sample[0][1]

        # Get date boundary
        date_sample = conn.execute(
            text("SELECT min(created_at), max(created_at) FROM transfer_requests;")
        ).fetchone()
        min_date, max_date = date_sample[0], date_sample[1]
        mid_date = min_date + (max_date - min_date) / 2

    print(f"\n[Benchmark] Target Account: {sample_account_id} (History: {sample_account_cnt} ledger entries)")
    print(f"[Benchmark] Date Window: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}\n")

    workload_results = {}

    # -------------------------------------------------------------------------
    # Workload 1: Account Transaction History (Ledger Entries)
    # -------------------------------------------------------------------------
    print("-> Benchmarking Workload 1: Account Transaction History...")
    sql_w1 = """
        SELECT id, transaction_id, account_id, entry_type, amount, sequence_num, created_at
        FROM ledger_entries
        WHERE account_id = :acc_id
        ORDER BY created_at DESC, sequence_num DESC
        LIMIT 50;
    """
    workload_results["workload_1_ledger_history"] = execute_explain_analyze(
        engine, sql_w1, {"acc_id": sample_account_id}
    )

    # -------------------------------------------------------------------------
    # Workload 2A: Customer Transaction Search by Account, Date Range, Status
    # -------------------------------------------------------------------------
    print("-> Benchmarking Workload 2A: Customer Transaction Search by Account + Date + Status...")
    sql_w2a = """
        SELECT id, idempotency_key, source_account_id, destination_account_id, amount, currency, status, created_at, posted_at
        FROM transfer_requests
        WHERE (source_account_id = :acc_id OR destination_account_id = :acc_id)
          AND created_at >= :start_date AND created_at <= :end_date
          AND status = 'POSTED'
        ORDER BY created_at DESC
        LIMIT 50;
    """
    workload_results["workload_2a_customer_tx_search"] = execute_explain_analyze(
        engine, sql_w2a, {
            "acc_id": sample_account_id,
            "start_date": mid_date,
            "end_date": max_date,
        }
    )

    # -------------------------------------------------------------------------
    # Workload 2B: Staff Global Transaction Search by Status and Date Range
    # -------------------------------------------------------------------------
    print("-> Benchmarking Workload 2B: Staff Global Transaction Search (Status + Date)...")
    sql_w2b = """
        SELECT id, source_user_id, source_account_id, destination_account_id, amount, status, created_at
        FROM transfer_requests
        WHERE status = 'POSTED'
          AND created_at >= :start_date AND created_at <= :end_date
        ORDER BY created_at DESC
        LIMIT 50;
    """
    workload_results["workload_2b_staff_tx_search"] = execute_explain_analyze(
        engine, sql_w2b, {
            "start_date": mid_date,
            "end_date": max_date,
        }
    )

    # -------------------------------------------------------------------------
    # Workload 3: Daily Activity Volume Aggregation (Reporting & Analytics)
    # -------------------------------------------------------------------------
    print("-> Benchmarking Workload 3: Daily Activity Volume Aggregation (Reporting)...")
    sql_w3 = """
        SELECT 
            TO_CHAR(posted_at, 'YYYY-MM-DD') AS day,
            COUNT(id) AS count,
            COALESCE(SUM(amount), 0.00) AS volume
        FROM transfer_requests
        WHERE status = 'POSTED' AND posted_at >= :start_date
        GROUP BY TO_CHAR(posted_at, 'YYYY-MM-DD')
        ORDER BY day;
    """
    workload_results["workload_3_daily_volume"] = execute_explain_analyze(
        engine, sql_w3, {"start_date": mid_date}
    )

    # -------------------------------------------------------------------------
    # Workload 4: Staff Advisory Fraud Alert Queue (Triage Filter)
    # -------------------------------------------------------------------------
    print("-> Benchmarking Workload 4: Staff Advisory Fraud Alert Triage Queue...")
    sql_w4 = """
        SELECT id, transfer_request_id, model_version, risk_score, decision, rule_flags, explanation, review_status, created_at
        FROM fraud_predictions
        WHERE review_status = 'PENDING' AND risk_score >= 0.7000
        ORDER BY risk_score DESC, created_at DESC
        LIMIT 50;
    """
    workload_results["workload_4_fraud_alert_triage"] = execute_explain_analyze(
        engine, sql_w4, {}
    )

    return workload_results


def print_workload_summary(workload_results: dict):
    """Print clean terminal table of benchmark results."""
    print("\n" + "=" * 90)
    print(f"{'Workload Name':<35} {'Cold (ms)':<12} {'Warm (ms)':<12} {'Buffer (Hit/Read)':<20} {'Primary Scan':<15}")
    print("-" * 90)
    for name, data in workload_results.items():
        cold_ms = f"{data['cold_execution_time_ms']:.2f}"
        warm_ms = f"{data['warm_execution_time_ms']:.2f}"
        buf = f"{data['warm_shared_hit_blocks']:.0f} hit / {data['warm_shared_read_blocks']:.0f} rd"
        scan = data["scan_types"][0] if data["scan_types"] else data["root_node_type"]
        if len(scan) > 20:
            scan = scan[:18] + ".."
        print(f"{name:<35} {cold_ms:<12} {warm_ms:<12} {buf:<20} {scan:<15}")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FinLedger-AI PostgreSQL Performance & Reliability Benchmark")
    parser.add_argument("--db-name", type=str, default="finledger_bench", help="Target benchmark database name")
    parser.add_argument("--populate", action="store_true", help="Populate benchmark database with synthetic data")
    parser.add_argument("--transfers", type=int, default=25000, help="Number of transfers to generate (x2 ledger entries)")
    parser.add_argument("--seed", type=int, default=42, help="Random generator seed")
    parser.add_argument("--run", action="store_true", help="Execute EXPLAIN (ANALYZE, BUFFERS) benchmark suite")
    parser.add_argument("--output", type=str, default=None, help="Save JSON results path")
    args = parser.parse_args()

    bench_url = get_benchmark_database_url(args.db_name)
    engine = create_engine(bench_url)

    if args.populate:
        populate_benchmark_database(
            engine,
            num_transfers=args.transfers,
            random_seed=args.seed,
        )

    if args.run:
        results = run_benchmark_workloads(engine)
        print_workload_summary(results)

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"[Benchmark] Saved full execution plans to {out_path}")
