"""Correction reversals for FinLedger-AI.

Committed ledger entries are append-only, so a mistaken or fraudulent customer transfer is
corrected by posting a new, balanced CORRECTION_REVERSAL transaction in the opposite
direction (AGENTS.md §3.4). The original transfer is marked REVERSED; its legs never change.
"""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger import LedgerTransaction
from app.models.transfer import TransferRequest
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.ledger_service import LedgerService
from app.services.transfer_service import lock_accounts_canonically


class ReversalError(Exception):
    """Business rejection of a reversal request."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def reversal_key(original_id: uuid.UUID) -> str:
    """Deterministic idempotency key tying a reversal to the transfer it corrects."""
    return f"reversal-{original_id}"


class ReversalService:
    """Posts balanced corrections for customer transfers."""

    @staticmethod
    def reverse_transfer(
        db: Session,
        transfer_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        reason: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> TransferRequest:
        """Reverse a POSTED customer transfer with a new balanced CORRECTION_REVERSAL posting.

        Locks the original transfer row first (so concurrent reversals serialise and the loser
        sees REVERSED), then both accounts in canonical order. The reversal, the status change
        and the success audit row commit atomically. Failures move no money and are audited
        in an independent transaction.

        Raises:
            ReversalError: 404 unknown transfer, 409 already reversed, 400 otherwise.
        """
        try:
            original = db.scalars(
                select(TransferRequest).where(TransferRequest.id == transfer_id).with_for_update()
            ).first()
            if original is None:
                raise ReversalError("Transfer not found", status_code=404)
            if original.status == "REVERSED":
                raise ReversalError("This transfer has already been reversed", status_code=409)
            if original.status != "POSTED":
                raise ReversalError(f"Only posted transfers can be reversed (status is {original.status})")

            original_txn = db.scalars(
                select(LedgerTransaction).where(LedgerTransaction.transfer_request_id == original.id)
            ).first()
            if original_txn is None or original_txn.transaction_type != "CUSTOMER_TRANSFER":
                raise ReversalError("Only customer transfers can be reversed here; investment purchases are not")

            amount: Decimal = original.amount
            locked = lock_accounts_canonically(db, original.source_account_id, original.destination_account_id)
            debit_acc = locked[original.destination_account_id]  # money comes back from the recipient
            credit_acc = locked[original.source_account_id]

            if debit_acc.cached_balance < amount:
                raise ReversalError(
                    f"The recipient account now holds INR {debit_acc.cached_balance:,.2f}, less than the "
                    f"INR {amount:,.2f} to reverse. Nothing was moved; recover the funds another way."
                )

            now = datetime.now(timezone.utc)
            reversal = TransferRequest(
                idempotency_key=reversal_key(original.id),
                source_user_id=actor_user_id,
                request_hash=hashlib.sha256(f"reversal:{original.id}".encode()).hexdigest(),
                source_account_id=debit_acc.id,
                destination_account_id=credit_acc.id,
                amount=amount,
                currency=original.currency,
                status="POSTED",
                posted_at=now,
            )
            db.add(reversal)
            db.flush()

            LedgerService.post_balanced_transaction(
                db=db,
                transaction_type="CORRECTION_REVERSAL",
                description=f"Reversal of transfer {original.id}: {reason}"[:255],
                legs=[
                    {"account_id": debit_acc.id, "entry_type": "DEBIT", "amount": amount},
                    {"account_id": credit_acc.id, "entry_type": "CREDIT", "amount": amount},
                ],
                transfer_request_id=reversal.id,
            )
            debit_acc.cached_balance -= amount
            debit_acc.version += 1
            credit_acc.cached_balance += amount
            credit_acc.version += 1
            original.status = "REVERSED"

            # Success audit commits atomically with the correction itself
            AuditService.log_event(
                action="TRANSFER_REVERSED",
                entity_type="TRANSFER",
                entity_id=str(original.id),
                actor_user_id=actor_user_id,
                ip_address=client_ip,
                user_agent=user_agent,
                metadata={
                    "reversal_transfer_id": str(reversal.id),
                    "amount": str(amount),
                    "reason": reason,
                },
                db=db,
                independent_txn=False,
            )
            db.commit()
            db.refresh(reversal)
            return reversal

        except ReversalError as err:
            db.rollback()
            # Same FK safety as transfer failures: only reference an actor that exists
            actor_exists = db.get(User, actor_user_id) is not None
            AuditService.log_event(
                action="TRANSFER_REVERSAL_FAILED",
                entity_type="TRANSFER",
                entity_id=str(transfer_id),
                actor_user_id=actor_user_id if actor_exists else None,
                ip_address=client_ip,
                user_agent=user_agent,
                metadata={"reason": reason, "failure": err.message},
                db=db,
                independent_txn=True,
            )
            raise
