"""CLI Ledger Reconciliation Script for FinLedger-AI.

Audits all accounts by comparing cached balances against net sums of posted ledger legs.
Outputs a structured summary table and exits with non-zero status if discrepancies exist.
Does NOT modify or rewrite financial data.
"""

import sys
import argparse
from decimal import Decimal
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.ledger_service import LedgerService


def run_reconciliation(test_db: bool = False) -> int:
    """Run system-wide reconciliation and print summary."""
    db_name = settings.DB_TEST_NAME if test_db else settings.DB_NAME
    target_url = settings.sync_test_database_url if test_db else settings.sync_database_url

    print("=" * 70)
    print("FINLEDGER-AI — SYSTEM LEDGER RECONCILIATION AUDIT")
    print(f"Target Database: {db_name}")
    print("=" * 70)

    engine = create_engine(target_url, pool_pre_ping=True)
    with Session(engine) as session:
        report = LedgerService.reconcile_all_accounts(session)

    print(f"Timestamp (UTC):              {report.reconciled_at.isoformat()}")
    print(f"Total Accounts Audited:       {report.total_accounts_checked}")
    print(f"System Clearing Balance:      INR {report.system_clearing_balance:,.2f}")
    print(f"Total Customer Liabilities:   INR {report.total_customer_liabilities:,.2f}")
    print(f"Global Net Ledger Delta:      INR {report.global_net_ledger_delta:,.2f}")
    print(f"Discrepancy Count:            {report.discrepancy_count}")
    print("-" * 70)

    if report.discrepancies:
        print("[!] DISCREPANCIES DETECTED:")
        print(f"{'Account Number':<25} {'Cached Balance':<15} {'Derived Balance':<15} {'Discrepancy':<15}")
        print("-" * 70)
        for d in report.discrepancies:
            print(f"{d.account_number:<25} INR {d.cached_balance:>10,.2f} INR {d.derived_balance:>10,.2f} INR {d.discrepancy:>10,.2f}")
        print("-" * 70)
        print("[FAIL] Audit failed: System contains unbalanced accounts or corrupted balance cache.")
        return 1
    else:
        print("[OK] Reconciliation passed: All cached balances match posted ledger entries exactly.")
        print(f"[OK] Closed-ledger invariant satisfied: Global net delta is INR {report.global_net_ledger_delta:,.2f}.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit and reconcile FinLedger-AI ledger balances.")
    parser.add_argument("--test", action="store_true", help="Run audit against finledger_test database")
    args = parser.parse_args()

    sys.exit(run_reconciliation(test_db=args.test))
