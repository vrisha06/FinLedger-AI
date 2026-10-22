"""Ledger Service for FinLedger-AI.

Manages double-entry bookkeeping, ledger balance calculations,
and automated system-wide reconciliation against posted entries.
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
from typing import Any
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ledger import LedgerTransaction, LedgerEntry
from app.schemas.ledger import DiscrepancyItem, ReconciliationReport


class LedgerService:
    """Service providing core ledger calculations and double-entry postings."""

    @staticmethod
    def get_derived_balance(db: Session, account_id: uuid.UUID) -> Decimal:
        """Calculate the true financial balance directly from posted ledger entries.

        Accounting Convention:
        Customer accounts (Liabilities): Credits increase balance, Debits decrease balance.
        Clearing account (Asset/Contra): Credits increase balance, Debits decrease balance.

        Returns:
            Decimal: Net sum of credits minus debits.
        """
        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (LedgerEntry.entry_type == "CREDIT", LedgerEntry.amount),
                            else_=-LedgerEntry.amount,
                        )
                    ),
                    Decimal("0.00"),
                )
            )
            .where(LedgerEntry.account_id == account_id)
        )
        balance = db.scalar(stmt)
        return balance if balance is not None else Decimal("0.00")

    @staticmethod
    def post_balanced_transaction(
        db: Session,
        transaction_type: str,
        description: str,
        legs: list[dict[str, Any]],
        transfer_request_id: uuid.UUID | None = None,
    ) -> LedgerTransaction:
        """Create and persist a balanced multi-row ledger transaction.

        Args:
            db: Active database session within an outer transaction.
            transaction_type: Type of transaction (e.g. 'CUSTOMER_TRANSFER', 'INITIAL_DEPOSIT').
            description: Narrative or memo describing the posting.
            legs: List of entry leg dicts containing:
                - account_id: UUID
                - entry_type: 'DEBIT' or 'CREDIT'
                - amount: Decimal (positive)
            transfer_request_id: Optional link to the originating transfer request.

        Raises:
            ValueError: If legs are unbalanced or invalid amounts are supplied.

        Returns:
            LedgerTransaction: The created transaction header with attached entry legs.
        """
        if not legs or len(legs) < 2:
            raise ValueError("A double-entry transaction must contain at least 2 legs")

        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        for leg in legs:
            amount = leg.get("amount")
            entry_type = leg.get("entry_type")
            if not isinstance(amount, Decimal) or amount <= Decimal("0.00"):
                raise ValueError(f"Each ledger leg must have a positive Decimal amount, got: {amount}")

            if entry_type == "DEBIT":
                total_debits += amount
            elif entry_type == "CREDIT":
                total_credits += amount
            else:
                raise ValueError(f"Invalid entry_type: {entry_type}. Must be 'DEBIT' or 'CREDIT'")

        if total_debits != total_credits:
            raise ValueError(
                f"Ledger transaction is unbalanced: total debits ({total_debits}) != total credits ({total_credits})"
            )

        txn = LedgerTransaction(
            transaction_type=transaction_type,
            description=description,
            transfer_request_id=transfer_request_id,
        )
        db.add(txn)
        db.flush()

        for idx, leg in enumerate(legs):
            entry = LedgerEntry(
                transaction_id=txn.id,
                account_id=leg["account_id"],
                entry_type=leg["entry_type"],
                amount=leg["amount"],
                sequence_num=idx + 1,
            )
            db.add(entry)

        db.flush()
        return txn

    @staticmethod
    def reconcile_accounts(
        db: Session,
        account_ids: list[uuid.UUID] | None = None,
    ) -> ReconciliationReport:
        """Audit accounts by comparing cached balances with ledger-derived sums.

        Never alters database rows or rewrites balances. Purely detects,
        measures, and reports discrepancies across audited accounts.

        Args:
            db: Database session.
            account_ids: Optional list of account UUIDs to audit. If None, audits all accounts in the database.

        Returns:
            ReconciliationReport: Audit report with discrepancy details.
        """
        # Fetch accounts ordered by account number
        accounts_stmt = select(Account).order_by(Account.account_number.asc())
        if account_ids is not None:
            accounts_stmt = accounts_stmt.where(Account.id.in_(account_ids))
        accounts = list(db.scalars(accounts_stmt).all())

        discrepancies: list[DiscrepancyItem] = []
        total_clearing = Decimal("0.00")
        total_customer_liabilities = Decimal("0.00")

        for acc in accounts:
            derived = LedgerService.get_derived_balance(db, acc.id)
            cached = acc.cached_balance
            diff = cached - derived

            if diff != Decimal("0.00"):
                discrepancies.append(
                    DiscrepancyItem(
                        account_id=acc.id,
                        account_number=acc.account_number,
                        cached_balance=cached,
                        derived_balance=derived,
                        discrepancy=diff,
                    )
                )

            if acc.account_type == "INTERNAL_CLEARING":
                total_clearing += cached
            else:
                total_customer_liabilities += cached

        # In a closed double-entry system:
        # System clearing contra-balance + customer account balances == 0.00
        global_net_delta = total_clearing + total_customer_liabilities
        if account_ids is None:
            is_balanced = len(discrepancies) == 0 and global_net_delta == Decimal("0.00")
        else:
            # For a targeted set of accounts, balanced if 0 discrepancies exist
            # and if clearing contra-account is included, net delta is 0
            has_clearing = any(acc.account_type == "INTERNAL_CLEARING" for acc in accounts)
            if has_clearing:
                is_balanced = len(discrepancies) == 0 and global_net_delta == Decimal("0.00")
            else:
                is_balanced = len(discrepancies) == 0

        return ReconciliationReport(
            reconciled_at=datetime.now(timezone.utc),
            total_accounts_checked=len(accounts),
            discrepancy_count=len(discrepancies),
            is_balanced=is_balanced,
            system_clearing_balance=total_clearing,
            total_customer_liabilities=total_customer_liabilities,
            global_net_ledger_delta=global_net_delta,
            discrepancies=discrepancies,
        )

    @staticmethod
    def reconcile_all_accounts(db: Session) -> ReconciliationReport:
        """Audit all accounts across the entire database."""
        return LedgerService.reconcile_accounts(db, account_ids=None)
