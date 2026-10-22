"""Transfer Engine Service for FinLedger-AI.

Implements atomic transfers, canonical row locking, scoped idempotency,
balanced double-entry ledger postings, and two-phase audit persistence on failure.
"""

from decimal import Decimal
import hashlib
import logging
import uuid
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.account import Account
from app.models.transfer import TransferRequest
from app.services.ledger_service import LedgerService
from app.services.audit_service import AuditService

logger = logging.getLogger("finledger.transfers")

class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with a different request payload."""


class TransferBusinessError(Exception):
    """Base class for transfer business rule rejections."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class InsufficientFundsError(TransferBusinessError):
    """Raised when the source account lacks sufficient funds."""

    def __init__(self, message: str = "Insufficient funds in source account"):
        super().__init__(message, status_code=400)


class TransferOwnershipError(TransferBusinessError):
    """Raised when the caller is unauthorized to debit the source account."""

    def __init__(self, message: str = "Unauthorized: Source account does not belong to caller"):
        super().__init__(message, status_code=403)


class AccountEligibilityError(TransferBusinessError):
    """Raised when an account is not in an eligible state for transfer."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


def lock_accounts_canonically(db: Session, *account_ids: uuid.UUID) -> dict[uuid.UUID, Account]:
    """Acquire FOR UPDATE row locks in canonical ascending primary key order (deadlock-free)."""
    lock_stmt = (
        select(Account)
        .where(Account.id.in_(sorted(set(account_ids))))
        .order_by(Account.id.asc())
        .with_for_update()
    )
    return {acc.id: acc for acc in db.scalars(lock_stmt).all()}


def compute_request_hash(
    source_account_id: uuid.UUID,
    destination_account_id: uuid.UUID,
    amount: Decimal,
    currency: str,
) -> str:
    """Generate SHA-256 fingerprint from canonical transfer request parameters."""
    canonical_repr = f"{source_account_id}:{destination_account_id}:{amount:.2f}:{currency}"
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


class TransferService:
    """Service orchestrating atomic, concurrency-safe financial transfers."""

    @staticmethod
    def execute_transfer(
        db: Session,
        caller_user_id: uuid.UUID,
        idempotency_key: str,
        source_account_id: uuid.UUID,
        destination_account_id: uuid.UUID,
        amount: Decimal,
        currency: str = "INR",
        memo: str | None = None,
        is_staff_override: bool = False,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[TransferRequest, bool]:
        """Execute an atomic financial transfer between accounts.

        Lifecycle:
        1. Validate request parameters & compute canonical SHA-256 request hash.
        2. Verify scoped idempotency (source_user_id, idempotency_key).
        3. Acquire row-level locks on both accounts in canonical ascending UUID order.
        4. Validate ownership, status, currency, and available balance under locks.
        5. If validation fails: rollback financial transaction, persist FAILED transfer & audit log
           in an independent transaction, and raise exception.
        6. On success: create TransferRequest, balanced LedgerTransaction and LedgerEntry legs,
           update cached balances atomically, commit, and record audit log.

        Returns:
            tuple[TransferRequest, bool]: The transfer record and a boolean indicating
            whether this was an idempotent replay (True) or new execution (False).
        """
        request_hash = compute_request_hash(
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            currency=currency,
        )

        # Step 1: Scoped Idempotency preliminary check
        replay = TransferService._find_replay(db, caller_user_id, idempotency_key, request_hash)
        if replay:
            return replay, True

        try:
            try:
                # Preliminary structural validation
                if source_account_id == destination_account_id:
                    raise TransferBusinessError("Source and destination accounts must be distinct")
                if amount <= Decimal("0.00"):
                    raise TransferBusinessError("Transfer amount must be strictly positive")
                if currency != "INR":
                    raise TransferBusinessError(f"Unsupported currency '{currency}'; only INR is supported")

                # Step 2: Acquire locks in canonical ascending UUID order
                locked_accounts = lock_accounts_canonically(db, source_account_id, destination_account_id)

                # A concurrent duplicate may have committed while we waited on the locks;
                # re-check under lock so the loser replays the winner instead of failing.
                replay = TransferService._find_replay(db, caller_user_id, idempotency_key, request_hash)
                if replay:
                    return replay, True

                # Step 3: Validate accounts under acquired locks
                source_acc = locked_accounts.get(source_account_id)
                dest_acc = locked_accounts.get(destination_account_id)

                if not source_acc:
                    raise AccountEligibilityError("Source account not found")
                if not dest_acc:
                    raise AccountEligibilityError("Destination account not found")

                # Ownership check (customers can only debit their own accounts)
                if not is_staff_override:
                    if not source_acc.customer or source_acc.customer.user_id != caller_user_id:
                        raise TransferOwnershipError(
                            "Unauthorized: Source account does not belong to the authenticated user"
                        )

                if source_acc.status != "ACTIVE":
                    raise AccountEligibilityError(f"Source account is {source_acc.status}, transfers not permitted")
                if dest_acc.status != "ACTIVE":
                    raise AccountEligibilityError(
                        f"Destination account is {dest_acc.status}, transfers not permitted"
                    )

                # Account type check: clearing and investment holding accounts only move through
                # their dedicated deposit / investment endpoints.
                account_types = {source_acc.account_type, dest_acc.account_type}
                if "INTERNAL_CLEARING" in account_types:
                    raise AccountEligibilityError(
                        "Transfers involving internal clearing accounts must use system deposit endpoints"
                    )
                if "INVESTMENT" in account_types:
                    raise AccountEligibilityError(
                        "Investment holding accounts cannot be used in transfers; use the investment endpoints"
                    )

                # Sufficient funds verification under row lock
                if source_acc.cached_balance < amount:
                    raise InsufficientFundsError(
                        f"Insufficient funds: available balance is {source_acc.cached_balance:.2f} INR, "
                        f"transfer amount is {amount:.2f} INR"
                    )
            except TransferBusinessError as err:
                TransferService._persist_failure_and_audit(
                    db=db,
                    caller_user_id=caller_user_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    source_account_id=source_account_id,
                    destination_account_id=destination_account_id,
                    amount=amount,
                    currency=currency,
                    failure_reason=err.message,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
                raise

            # Step 4: Create TransferRequest record
            transfer_req = TransferRequest(
                idempotency_key=idempotency_key,
                source_user_id=caller_user_id,
                request_hash=request_hash,
                source_account_id=source_account_id,
                destination_account_id=destination_account_id,
                amount=amount,
                currency=currency,
                status="POSTED",
                posted_at=func.now(),
            )
            db.add(transfer_req)
            db.flush()

            # Step 5: Post balanced double-entry ledger entries
            # Customer accounts are liabilities:
            # - Debit source account: decreases liability (balance)
            # - Credit destination account: increases liability (balance)
            legs = [
                {
                    "account_id": source_acc.id,
                    "entry_type": "DEBIT",
                    "amount": amount,
                },
                {
                    "account_id": dest_acc.id,
                    "entry_type": "CREDIT",
                    "amount": amount,
                },
            ]

            description = memo or f"Transfer from {source_acc.account_number} to {dest_acc.account_number}"
            LedgerService.post_balanced_transaction(
                db=db,
                transaction_type="CUSTOMER_TRANSFER",
                description=description,
                legs=legs,
                transfer_request_id=transfer_req.id,
            )

            # Step 6: Atomically update cached balances
            source_acc.cached_balance -= amount
            source_acc.version += 1

            dest_acc.cached_balance += amount
            dest_acc.version += 1

            # Step 7: Commit transaction
            # Triggers PostgreSQL deferred constraint trigger trg_verify_ledger_balance
            db.commit()
            db.refresh(transfer_req)

            # Step 8: Audit log success in independent transaction
            AuditService.log_event(
                action="TRANSFER_POSTED",
                entity_type="TRANSFER",
                entity_id=str(transfer_req.id),
                actor_user_id=caller_user_id,
                ip_address=client_ip,
                user_agent=user_agent,
                metadata={
                    "idempotency_key": idempotency_key,
                    "source_account_id": str(source_account_id),
                    "destination_account_id": str(destination_account_id),
                    "amount": str(amount),
                    "currency": currency,
                    "status": "POSTED",
                },
                db=db,
                independent_txn=True,
            )

            # Step 9: Post-commit Advisory Fraud Scoring (strictly advisory, outside row locks)
            # Scoring failures are safely contained and never affect the committed financial transfer.
            try:
                from ml.predict import fraud_detector
                fraud_detector.score_transfer(transfer_req, db=db)
            except Exception:
                logger.exception("Advisory fraud scoring failed for transfer %s", transfer_req.id)

            # Step 10: Post-commit Payee Edge update & LedgerGraph Analysis (strictly advisory)
            try:
                from app.services.payee_guard_service import PayeeGuardService
                from app.services.ledger_graph_service import LedgerGraphService

                PayeeGuardService.record_transfer_edge(
                    db=db,
                    source_account_id=source_account_id,
                    destination_account_id=destination_account_id,
                    amount=amount,
                )
                db.commit()

                LedgerGraphService.analyze_transaction(
                    db=db,
                    transfer_request_id=transfer_req.id,
                    persist=True,
                )
            except Exception:
                logger.exception("Advisory payee/graph analysis failed for transfer %s", transfer_req.id)
                db.rollback()

            return transfer_req, False

        except IntegrityError as exc:
            # Handle concurrent duplicate requests hitting uq_transfers_user_idempotency
            db.rollback()
            # Check if this was a uniqueness conflict on idempotency key
            orig_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
            if "uq_transfers_user_idempotency" in orig_msg:
                # Query winner from clean query
                target_engine = db.get_bind()
                with Session(target_engine, expire_on_commit=False) as check_db:
                    winner = TransferService._find_replay(check_db, caller_user_id, idempotency_key, request_hash)
                    if winner:
                        return winner, True
            raise

    @staticmethod
    def _find_replay(
        db: Session,
        caller_user_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
    ) -> TransferRequest | None:
        """Resolve a scoped idempotency key to its original transfer.

        Raises:
            IdempotencyConflictError: the key was used with a different payload.
            TransferBusinessError: the original attempt FAILED; a replay must surface that
                failure rather than a 2xx receipt for a transfer that never moved money.
        """
        existing_req = db.scalars(
            select(TransferRequest).where(
                TransferRequest.source_user_id == caller_user_id,
                TransferRequest.idempotency_key == idempotency_key,
            )
        ).first()
        if not existing_req:
            return None
        if existing_req.request_hash != request_hash:
            raise IdempotencyConflictError(
                "Idempotency key reuse conflict: request parameters differ from original submission"
            )
        if existing_req.status == "FAILED":
            raise TransferBusinessError(existing_req.failure_reason or "Previous attempt with this key failed")
        return existing_req

    @staticmethod
    def _persist_failure_and_audit(
        db: Session,
        caller_user_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
        source_account_id: uuid.UUID | None,
        destination_account_id: uuid.UUID | None,
        amount: Decimal,
        currency: str,
        failure_reason: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Roll back the financial transaction and record the failure and audit trail independently.

        Ensures financial state remains untouched while preserving forensic audit evidence.
        """
        # Completely roll back financial transaction
        db.rollback()

        target_engine = db.get_bind() if db is not None else SessionLocal.kw.get("bind")
        with Session(target_engine) as audit_db:
            transfer_id = None
            # Validate foreign keys exist in target database before creating FK-dependent rows
            from app.models.user import User

            actor_exists = (
                audit_db.scalars(select(User.id).where(User.id == caller_user_id)).first() is not None
                if caller_user_id
                else False
            )
            valid_actor_id = caller_user_id if actor_exists else None

            src_exists = (
                audit_db.scalars(select(Account.id).where(Account.id == source_account_id)).first() is not None
                if source_account_id
                else False
            )
            dst_exists = (
                audit_db.scalars(select(Account.id).where(Account.id == destination_account_id)).first() is not None
                if destination_account_id
                else False
            )

            # Only record TransferRequest if valid foreign keys are present in database
            if valid_actor_id and src_exists and dst_exists:
                try:
                    failed_req = TransferRequest(
                        idempotency_key=idempotency_key,
                        source_user_id=valid_actor_id,
                        request_hash=request_hash,
                        source_account_id=source_account_id,
                        destination_account_id=destination_account_id,
                        amount=amount if amount > Decimal("0.00") else Decimal("0.01"),
                        currency=currency,
                        status="FAILED",
                        failure_reason=failure_reason,
                    )
                    audit_db.add(failed_req)
                    audit_db.commit()
                    transfer_id = failed_req.id
                except Exception:
                    audit_db.rollback()

            # Record audit log
            AuditService.log_event(
                action="TRANSFER_FAILED",
                entity_type="TRANSFER",
                entity_id=str(transfer_id or idempotency_key),
                actor_user_id=valid_actor_id,
                ip_address=client_ip,
                user_agent=user_agent,
                metadata={
                    "idempotency_key": idempotency_key,
                    "source_account_id": str(source_account_id) if source_account_id else None,
                    "destination_account_id": str(destination_account_id) if destination_account_id else None,
                    "amount": str(amount),
                    "reason": failure_reason,
                },
                db=audit_db,
                independent_txn=False,
            )
            audit_db.commit()
