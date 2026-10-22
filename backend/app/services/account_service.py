"""Account Service for FinLedger-AI.

Manages account retrieval, ledger history inspection, and simulated opening deposits
via the internal clearing account (INR-SYS-CLEARING).
"""

from decimal import Decimal
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account
from app.models.ledger import LedgerEntry
from app.services.ledger_service import LedgerService
from app.services.audit_service import AuditService


class AccountService:
    """Service managing customer account operations and simulated initial deposits."""

    @staticmethod
    def provision_customer_account(
        db: Session,
        customer_id: uuid.UUID,
        account_type: str = "SAVINGS",
    ) -> Account:
        """Provision a new customer account with zero initial cached balance.

        Zero initial balance ensures strict adherence to double-entry ledger invariants.
        Funding must be deposited against the internal clearing account.
        """
        if account_type not in ("SAVINGS", "CURRENT"):
            raise ValueError(f"Invalid account type '{account_type}' for customer provisioning")

        prefix = "SAV" if account_type == "SAVINGS" else "CUR"
        account_number = f"INR-{prefix}-{uuid.uuid4().hex[:8].upper()}"
        account = Account(
            customer_id=customer_id,
            account_number=account_number,
            account_type=account_type,
            currency=settings.DEFAULT_CURRENCY,
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        db.add(account)
        db.flush()
        return account

    @staticmethod
    def get_customer_accounts(db: Session, customer_id: uuid.UUID) -> list[Account]:
        """Fetch all accounts belonging to a specific customer profile."""
        stmt = (
            select(Account)
            .where(Account.customer_id == customer_id)
            .order_by(Account.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_account_by_id(db: Session, account_id: uuid.UUID) -> Account | None:
        """Fetch an account by primary key UUID."""
        stmt = select(Account).where(Account.id == account_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_clearing_account(db: Session) -> Account:
        """Fetch the internal system clearing account.

        Raises:
            RuntimeError: If the system clearing account is missing from database.
        """
        stmt = select(Account).where(Account.account_number == settings.CLEARING_ACCOUNT_NUMBER)
        account = db.scalars(stmt).first()
        if not account:
            raise RuntimeError(
                f"Internal clearing account '{settings.CLEARING_ACCOUNT_NUMBER}' not initialized in database"
            )
        return account

    @staticmethod
    def get_account_ledger_entries(
        db: Session,
        account_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LedgerEntry]:
        """Retrieve historical ledger entries for an account, ordered chronologically descending."""
        stmt = (
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc(), LedgerEntry.sequence_num.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def deposit_opening_funds(
        db: Session,
        account_id: uuid.UUID,
        amount: Decimal,
        description: str = "Simulated Opening Deposit",
        actor_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Account:
        """Simulate an opening deposit via the internal clearing account (INR-SYS-CLEARING).

        Enforces double-entry convention:
        - Internal clearing account is DEBITED by amount.
        - Customer liability account is CREDITED by amount.
        - Cached balances are updated atomically within the same database transaction.
        - Row locks are acquired in canonical ascending primary key order to prevent deadlocks.

        Args:
            db: Active database session.
            account_id: Customer account to receive deposit.
            amount: Strictly positive Decimal amount.
            description: Narrative description for the ledger entry.
            actor_user_id: ID of user initiating the deposit.
            ip_address: Client IP address for audit.
            user_agent: Client User-Agent for audit.

        Returns:
            Account: The updated customer account.
        """
        if amount <= Decimal("0.00"):
            raise ValueError("Deposit amount must be strictly positive")

        clearing_acc = AccountService.get_clearing_account(db)

        # Canonical lock ordering by UUID
        first_id, second_id = sorted([account_id, clearing_acc.id])
        lock_stmt = (
            select(Account)
            .where(Account.id.in_([first_id, second_id]))
            .order_by(Account.id.asc())
            .with_for_update()
        )
        locked = {acc.id: acc for acc in db.scalars(lock_stmt).all()}

        target_acc = locked.get(account_id)
        if not target_acc:
            raise ValueError("Target account not found")

        clearing_locked = locked.get(clearing_acc.id)
        if not clearing_locked:
            raise RuntimeError("Failed to acquire lock on clearing account")

        if target_acc.status != "ACTIVE":
            raise ValueError(f"Target account status is {target_acc.status}, deposit rejected")

        # Prepare balanced double-entry legs
        # Customer account (Liability): CREDIT increases balance
        # Clearing account (Asset/Contra): DEBIT balances the credit
        legs = [
            {
                "account_id": clearing_locked.id,
                "entry_type": "DEBIT",
                "amount": amount,
            },
            {
                "account_id": target_acc.id,
                "entry_type": "CREDIT",
                "amount": amount,
            },
        ]

        LedgerService.post_balanced_transaction(
            db=db,
            transaction_type="INITIAL_DEPOSIT",
            description=description,
            legs=legs,
        )

        # Atomically update cached balances
        clearing_locked.cached_balance -= amount
        clearing_locked.version += 1

        target_acc.cached_balance += amount
        target_acc.version += 1

        db.commit()
        db.refresh(target_acc)

        AuditService.log_event(
            action="INITIAL_DEPOSIT",
            entity_type="ACCOUNT",
            entity_id=str(target_acc.id),
            actor_user_id=actor_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "account_number": target_acc.account_number,
                "amount": str(amount),
                "new_balance": str(target_acc.cached_balance),
                "description": description,
            },
            db=db,
            independent_txn=True,
        )

        return target_acc
