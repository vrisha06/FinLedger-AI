"""PayeeGuard: Pre-transfer Recipient Verification & Advisory Review Service.

Operational Invariants:
1. Preview never moves funds, reserves balances, or generates ledger postings.
2. Server-side authorization: Validates source account ownership strictly against caller_user_id.
3. Information boundary: Authoritatively verifies legal beneficiary name from database records
   while masking sensitive account numbers and redacting private KYC data.
4. Distinguishes first-time beneficiaries and flags material deviations from account history.
5. Clearly disclaimed as internal FinLedger-AI account verification.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError

from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.payee import PayeeEdge, SavedPayee
from app.models.customer import Customer


class PayeeGuardError(Exception):
    """Base exception for PayeeGuard validation failures."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PayeeGuardService:
    """Beneficiary pre-confirmation verification service."""

    @staticmethod
    def preview_transfer(
        db: Session,
        caller_user_id: uuid.UUID,
        source_account_id: uuid.UUID,
        destination_account_id: uuid.UUID | None,
        amount: Decimal,
        is_staff: bool = False,
        destination_account_number: str | None = None,
    ) -> Dict[str, Any]:
        """Perform authoritative pre-submission beneficiary verification and safety checks.

        The recipient may be given by account ID or by account number (case-insensitive);
        the response always carries the resolved authoritative destination_account_id.
        """
        # 0. Resolve a human-entered account number to the authoritative account
        if destination_account_id is None:
            number = (destination_account_number or "").strip().upper()
            destination_account_id = db.scalars(
                select(Account.id).where(Account.account_number == number)
            ).first()
            if destination_account_id is None:
                raise PayeeGuardError(
                    "No account found with that account number. Check it and try again.",
                    status_code=404,
                )

        # 1. Structural checks
        if source_account_id == destination_account_id:
            raise PayeeGuardError("Source and destination accounts must be distinct", status_code=400)

        if amount <= Decimal("0.00"):
            raise PayeeGuardError("Transfer amount must be strictly positive", status_code=400)

        # 2. Source Account Validation & Ownership Enforcement
        source_acc = db.get(Account, source_account_id)
        if not source_acc:
            raise PayeeGuardError("Source account not found", status_code=404)

        if not is_staff:
            if not source_acc.customer or source_acc.customer.user_id != caller_user_id:
                raise PayeeGuardError("Forbidden: You do not own the selected source account", status_code=403)

        if source_acc.status != "ACTIVE":
            raise PayeeGuardError(f"Source account is currently {source_acc.status}", status_code=400)

        if source_acc.account_type == "INTERNAL_CLEARING":
            raise PayeeGuardError("Transfers from internal clearing accounts are prohibited", status_code=400)

        if source_acc.cached_balance < amount:
            raise PayeeGuardError(
                f"Insufficient funds: Available balance is ₹{source_acc.cached_balance:,.2f}, required ₹{amount:,.2f}",
                status_code=400,
            )

        # 3. Destination Account Verification
        dest_acc = db.get(Account, destination_account_id)
        if not dest_acc:
            raise PayeeGuardError(
                "Recipient account not found. Please verify the destination account ID.",
                status_code=404,
            )

        if dest_acc.status != "ACTIVE":
            raise PayeeGuardError(
                f"Recipient account cannot receive transfers (Status: {dest_acc.status})",
                status_code=400,
            )

        if dest_acc.account_type == "INTERNAL_CLEARING":
            raise PayeeGuardError(
                "Direct transfers to internal clearing accounts are prohibited",
                status_code=400,
            )

        if "INVESTMENT" in (source_acc.account_type, dest_acc.account_type):
            raise PayeeGuardError(
                "Investment holding accounts cannot be used in transfers; use the investment endpoints",
                status_code=400,
            )

        # 4. Authoritative Recipient Display Data
        dest_customer = dest_acc.customer
        recipient_name = dest_customer.full_name if dest_customer else "FinLedger System Account"

        # Mask account number: e.g. "ACC-SAV-0001" -> "ACC-••••-0001"
        acc_raw = dest_acc.account_number
        if len(acc_raw) > 6:
            prefix = acc_raw[:4]
            suffix = acc_raw[-4:]
            masked_acc = f"{prefix}••••{suffix}"
        else:
            masked_acc = "••••" + acc_raw[-2:]

        # 5. Check Historical Relationship (First-time Recipient Check)
        past_transfers_stmt = (
            select(
                func.count(TransferRequest.id),
                func.max(TransferRequest.created_at),
                func.avg(TransferRequest.amount),
            )
            .where(
                and_(
                    TransferRequest.source_account_id == source_account_id,
                    TransferRequest.destination_account_id == destination_account_id,
                    TransferRequest.status == "POSTED",
                )
            )
        )
        row = db.execute(past_transfers_stmt).first()
        prior_count = row[0] if row and row[0] is not None else 0
        last_transferred_at = row[1] if row and row[1] is not None else None
        is_first_time = (prior_count == 0)

        # Check for saved payee nickname
        saved_payee_stmt = select(SavedPayee).where(
            and_(
                SavedPayee.customer_id == source_acc.customer_id,
                SavedPayee.payee_account_id == destination_account_id,
            )
        )
        saved_payee = db.scalars(saved_payee_stmt).first()
        payee_nickname = saved_payee.nickname if saved_payee else None

        # 6. Advisory Historical Deviation Check
        warnings: List[str] = []
        if is_first_time:
            warnings.append(
                "First-Time Recipient: You have never sent money to this account before. "
                "Please verify the legal name matches your intended beneficiary."
            )

        # Check customer average transfer size deviation
        user_history_stmt = (
            select(func.avg(TransferRequest.amount))
            .where(
                and_(
                    TransferRequest.source_account_id == source_account_id,
                    TransferRequest.status == "POSTED",
                )
            )
        )
        user_avg = db.scalar(user_history_stmt)
        if user_avg and user_avg > Decimal("0"):
            avg_dec = Decimal(str(user_avg))
            if amount >= avg_dec * Decimal("3.0") and amount >= Decimal("20000.00"):
                warnings.append(
                    f"Unusual Amount: Transfer of ₹{amount:,.2f} is more than 3x your historical average "
                    f"(average: ₹{avg_dec:,.2f}). Ensure you trust the recipient."
                )

        return {
            "source_account_id": str(source_account_id),
            "source_account_number": source_acc.account_number,
            "source_available_balance": str(source_acc.cached_balance),
            "destination_account_id": str(destination_account_id),
            "recipient_legal_name": recipient_name,
            "masked_account_number": masked_acc,
            "account_type": dest_acc.account_type,
            "nickname": payee_nickname,
            "is_first_time_recipient": is_first_time,
            "prior_transfers_count": prior_count,
            "last_transferred_at": last_transferred_at.isoformat() if last_transferred_at else None,
            "amount": str(amount),
            "currency": "INR",
            "validation_status": "VERIFIED_ELIGIBLE",
            "advisory_warnings": warnings,
            "verification_provider": "Internal FinLedger-AI Account Holder Verification (NPCI / Core Banking Directory Reference)",
        }

    @staticmethod
    def record_transfer_edge(
        db: Session,
        source_account_id: uuid.UUID,
        destination_account_id: uuid.UUID,
        amount: Decimal,
        timestamp: Optional[datetime] = None,
    ) -> Optional[PayeeEdge]:
        """Update or create the authoritative money-flow edge between two accounts."""
        ts = timestamp or datetime.now(timezone.utc)
        try:
            with db.begin_nested():
                edge = db.scalars(
                    select(PayeeEdge).where(
                        and_(
                            PayeeEdge.source_account_id == source_account_id,
                            PayeeEdge.destination_account_id == destination_account_id,
                        )
                    ).with_for_update()
                ).first()

                if edge:
                    edge.transfer_count += 1
                    edge.total_amount += amount
                    edge.avg_amount = edge.total_amount / Decimal(edge.transfer_count)
                    edge.last_seen = ts
                else:
                    edge = PayeeEdge(
                        source_account_id=source_account_id,
                        destination_account_id=destination_account_id,
                        first_seen=ts,
                        last_seen=ts,
                        transfer_count=1,
                        total_amount=amount,
                        avg_amount=amount,
                    )
                    db.add(edge)
                db.flush()
                return edge
        except IntegrityError:
            # Another concurrent transaction inserted the edge simultaneously; update under row lock
            edge = db.scalars(
                select(PayeeEdge).where(
                    and_(
                        PayeeEdge.source_account_id == source_account_id,
                        PayeeEdge.destination_account_id == destination_account_id,
                    )
                ).with_for_update()
            ).first()
            if edge:
                edge.transfer_count += 1
                edge.total_amount += amount
                edge.avg_amount = edge.total_amount / Decimal(edge.transfer_count)
                edge.last_seen = ts
                db.flush()
                return edge
            return None
