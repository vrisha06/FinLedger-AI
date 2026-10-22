"""Investment Service for FinLedger-AI.

Orchestrates atomic double-entry simulated investment purchases,
holdings inspection, and customer portfolio aggregation.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import logging
import uuid
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User
from app.models.customer import Customer
from app.models.account import Account
from app.models.product import FinancialProduct, Investment
from app.models.transfer import TransferRequest
from app.models.ledger import LedgerTransaction, LedgerEntry
from app.services.audit_service import AuditService
from app.services.transfer_service import (
    TransferBusinessError,
    InsufficientFundsError,
    TransferOwnershipError,
    AccountEligibilityError,
    lock_accounts_canonically,
)

logger = logging.getLogger("finledger.investments")


class InvestmentProductError(TransferBusinessError):
    """Raised when the requested product is invalid, inactive, or below minimum."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


class InvestmentConflictError(TransferBusinessError):
    """Raised when an idempotency key is reused with conflicting parameters."""

    def __init__(self, message: str = "Idempotency key reuse with mismatched parameters"):
        super().__init__(message, status_code=409)


def compute_investment_request_hash(
    source_account_id: uuid.UUID,
    product_id: uuid.UUID,
    amount: Decimal,
    currency: str = "INR",
) -> str:
    """Generate SHA-256 fingerprint for investment purchase parameters."""
    canonical_repr = f"{source_account_id}:{product_id}:{amount:.2f}:{currency}"
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


class InvestmentService:
    """Service orchestrating simulated investment purchases and portfolio calculations."""

    @staticmethod
    def _persist_failure_and_audit(
        caller_user_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
        source_account_id: uuid.UUID | None,
        destination_account_id: uuid.UUID | None,
        amount: Decimal,
        currency: str,
        failure_reason: str,
        db: Session | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Persist failed investment attempt in an independent transaction."""
        # Roll back financial transaction first to release row-level locks
        if db is not None:
            try:
                db.rollback()
            except Exception:
                logger.exception("Rollback before investment failure audit failed")

        target_engine = db.get_bind() if db is not None else SessionLocal.kw.get("bind")
        with Session(target_engine) as isolated_db:
            transfer_id = None
            actor_exists = (
                isolated_db.scalars(select(User.id).where(User.id == caller_user_id)).first() is not None
                if caller_user_id
                else False
            )
            valid_actor_id = caller_user_id if actor_exists else None

            src_exists = (
                isolated_db.scalars(select(Account.id).where(Account.id == source_account_id)).first() is not None
                if source_account_id
                else False
            )
            dst_exists = (
                isolated_db.scalars(select(Account.id).where(Account.id == destination_account_id)).first() is not None
                if destination_account_id
                else False
            )

            if valid_actor_id and src_exists and dst_exists:
                try:
                    failed_req = TransferRequest(
                        source_user_id=valid_actor_id,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                        source_account_id=source_account_id,
                        destination_account_id=destination_account_id,
                        amount=amount if amount > Decimal("0.00") else Decimal("0.01"),
                        currency=currency,
                        status="FAILED",
                        failure_reason=failure_reason,
                    )
                    isolated_db.add(failed_req)
                    isolated_db.commit()
                    transfer_id = failed_req.id
                except Exception:
                    isolated_db.rollback()

            AuditService.log_event(
                action="INVESTMENT_PURCHASE_FAILED",
                entity_type="INVESTMENT",
                entity_id=str(transfer_id or idempotency_key),
                actor_user_id=valid_actor_id,
                ip_address=client_ip,
                user_agent=user_agent,
                metadata={
                    "failure_reason": failure_reason,
                    "amount": str(amount),
                    "source_account_id": str(source_account_id) if source_account_id else None,
                },
                db=isolated_db,
                independent_txn=False,
            )
            isolated_db.commit()

    @staticmethod
    def purchase_investment(
        db: Session,
        caller_user_id: uuid.UUID,
        idempotency_key: str,
        product_id: uuid.UUID,
        source_account_id: uuid.UUID,
        amount: Decimal,
        currency: str = "INR",
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Investment, bool]:
        """Purchase a simulated financial product via atomic double-entry posting.

        Enforces:
        - Customer ownership of the debiting account
        - Product availability and minimum subscription amount
        - Canonical row locking on accounts (min_id, max_id)
        - Atomic debit on savings account and credit on investment account
        - Scoped idempotency per customer (returns cached result on exact replay, 409 on conflict)
        - Atomic investment position creation with maturity calculation

        Returns:
            tuple[Investment, bool]: (Investment record, is_replay boolean)
        """
        request_hash = compute_investment_request_hash(
            source_account_id=source_account_id,
            product_id=product_id,
            amount=amount,
            currency=currency,
        )

        # Step 1: Idempotency preliminary check
        replay = InvestmentService._find_replay(db, caller_user_id, idempotency_key, request_hash)
        if replay:
            return replay, True

        inv_acc: Account | None = None
        try:
            # Step 2: Validate amount and currency
            if amount <= Decimal("0.00"):
                raise InvestmentProductError("Investment amount must be strictly positive")
            if currency != "INR":
                raise InvestmentProductError(f"Unsupported currency '{currency}'; only INR is supported")

            # Step 3: Validate customer profile and lock to prevent concurrent provisioning races
            customer = db.scalars(
                select(Customer).where(Customer.user_id == caller_user_id).with_for_update()
            ).first()
            if not customer:
                raise TransferOwnershipError("No customer profile found for caller")

            # A concurrent duplicate may have committed while we waited on the customer lock
            replay = InvestmentService._find_replay(db, caller_user_id, idempotency_key, request_hash)
            if replay:
                return replay, True

            # Step 4: Validate product availability & minimum amount
            product = db.get(FinancialProduct, product_id)
            if not product or not product.is_active:
                raise InvestmentProductError("Selected financial product is inactive or not found")
            if amount < product.min_amount:
                raise InvestmentProductError(
                    f"Investment amount INR {amount:,.2f} is below the product minimum of INR {product.min_amount:,.2f}"
                )

            # Step 5: Get or provision the customer's single INVESTMENT holding account.
            # Any status is looked up so a FROZEN/CLOSED holding account is rejected below
            # instead of colliding with its unique account number.
            inv_acc = db.scalars(
                select(Account).where(
                    Account.customer_id == customer.id,
                    Account.account_type == "INVESTMENT",
                )
            ).first()
            if not inv_acc:
                inv_acc = Account(
                    customer_id=customer.id,
                    account_number=f"INR-INV-{customer.id.hex[:8].upper()}",
                    account_type="INVESTMENT",
                    currency="INR",
                    cached_balance=Decimal("0.00"),
                    status="ACTIVE",
                    version=1,
                )
                db.add(inv_acc)
                db.flush()

            # Step 6: Acquire locks in canonical ascending UUID order
            locked_accounts = lock_accounts_canonically(db, source_account_id, inv_acc.id)
            source_acc = locked_accounts.get(source_account_id)
            dest_inv_acc = locked_accounts[inv_acc.id]

            if not source_acc:
                raise AccountEligibilityError("Source funding account not found")
            if source_acc.customer_id != customer.id:
                raise TransferOwnershipError(
                    "Unauthorized: Source funding account does not belong to authenticated customer"
                )
            if source_acc.status != "ACTIVE":
                raise AccountEligibilityError(
                    f"Source account status is '{source_acc.status}', debits not permitted"
                )
            if source_acc.account_type in ("INTERNAL_CLEARING", "INVESTMENT"):
                raise AccountEligibilityError(
                    f"Cannot purchase investments using account type '{source_acc.account_type}'"
                )
            if dest_inv_acc.status != "ACTIVE":
                raise AccountEligibilityError(
                    f"Investment holding account is {dest_inv_acc.status}, new subscriptions not permitted"
                )
            if source_acc.cached_balance < amount:
                raise InsufficientFundsError(
                    f"Insufficient funds: available INR {source_acc.cached_balance:,.2f}, required INR {amount:,.2f}"
                )

            # Step 7: Atomic Financial and Investment Postings
            now_utc = datetime.now(timezone.utc)
            maturity_date = now_utc + timedelta(days=product.term_months * 30)

            # 7a. TransferRequest master record
            transfer_req = TransferRequest(
                source_user_id=caller_user_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                source_account_id=source_acc.id,
                destination_account_id=dest_inv_acc.id,
                amount=amount,
                currency=currency,
                status="POSTED",
                posted_at=now_utc,
            )
            db.add(transfer_req)
            db.flush()

            # 7b. LedgerTransaction header
            ledger_txn = LedgerTransaction(
                transfer_request_id=transfer_req.id,
                transaction_type="INVESTMENT_PURCHASE",
                description=f"Investment purchase: {product.name} ({product.code})",
            )
            db.add(ledger_txn)
            db.flush()

            # 7c. Balanced LedgerEntry legs
            leg_debit = LedgerEntry(
                transaction_id=ledger_txn.id,
                account_id=source_acc.id,
                entry_type="DEBIT",
                amount=amount,
                sequence_num=1,
            )
            leg_credit = LedgerEntry(
                transaction_id=ledger_txn.id,
                account_id=dest_inv_acc.id,
                entry_type="CREDIT",
                amount=amount,
                sequence_num=2,
            )
            db.add_all([leg_debit, leg_credit])

            # 7d. Atomic balance updates
            source_acc.cached_balance -= amount
            source_acc.version += 1
            dest_inv_acc.cached_balance += amount
            dest_inv_acc.version += 1

            # 7e. Investment position record (start_date == transfer posted_at links the pair for replays)
            investment = Investment(
                customer_id=customer.id,
                account_id=dest_inv_acc.id,
                product_id=product.id,
                invested_amount=amount,
                current_value=amount,
                status="ACTIVE",
                start_date=now_utc,
                maturity_date=maturity_date,
            )
            db.add(investment)

            # Step 8: Commit transaction atomically
            db.commit()
            db.refresh(investment)

            AuditService.log_event(
                action="INVESTMENT_PURCHASED",
                entity_type="INVESTMENT",
                entity_id=str(investment.id),
                actor_user_id=caller_user_id,
                ip_address=client_ip,
                user_agent=user_agent,
                metadata={
                    "product_id": str(product.id),
                    "product_code": product.code,
                    "invested_amount": str(amount),
                    "term_months": product.term_months,
                    "annual_yield_rate": str(product.annual_yield_rate),
                    "transfer_request_id": str(transfer_req.id),
                },
                db=db,
                independent_txn=True,
            )

            return investment, False

        except TransferBusinessError as err:
            failure_reason, client_error = err.message, err
        except Exception as exc:
            # Never leak driver/SQL text to clients or to replayable failure reasons
            logger.exception("Investment purchase failed with an internal error")
            failure_reason = f"Internal error during investment purchase ({type(exc).__name__})"
            client_error = TransferBusinessError(
                "Investment purchase could not be completed due to an internal error", status_code=500
            )

        InvestmentService._persist_failure_and_audit(
            caller_user_id=caller_user_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            source_account_id=source_account_id,
            destination_account_id=inv_acc.id if inv_acc else None,
            amount=amount,
            currency=currency,
            failure_reason=failure_reason,
            db=db,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        raise client_error

    @staticmethod
    def _find_replay(
        db: Session,
        caller_user_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
    ) -> Investment | None:
        """Resolve a scoped idempotency key to the exact investment its original request created."""
        existing_req = db.scalars(
            select(TransferRequest).where(
                TransferRequest.source_user_id == caller_user_id,
                TransferRequest.idempotency_key == idempotency_key,
            )
        ).first()
        if not existing_req:
            return None
        if existing_req.request_hash != request_hash:
            raise InvestmentConflictError(
                f"Idempotency key '{idempotency_key}' already used with different investment parameters"
            )
        if existing_req.status == "FAILED":
            raise TransferBusinessError(f"Previous attempt failed: {existing_req.failure_reason}", status_code=400)
        return db.scalars(
            select(Investment).where(
                Investment.account_id == existing_req.destination_account_id,
                Investment.invested_amount == existing_req.amount,
                Investment.start_date == existing_req.posted_at,
            )
        ).first()

    @staticmethod
    def list_customer_investments(
        db: Session,
        customer_id: uuid.UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Investment]:
        """Fetch investment positions owned by a specific customer."""
        stmt = (
            select(Investment)
            .where(Investment.customer_id == customer_id)
        )
        if status is not None:
            stmt = stmt.where(Investment.status == status)
        stmt = stmt.order_by(Investment.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_investment_by_id(
        db: Session,
        investment_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
    ) -> Investment | None:
        """Fetch investment details, with optional customer ownership filter."""
        stmt = select(Investment).where(Investment.id == investment_id)
        if customer_id is not None:
            stmt = stmt.where(Investment.customer_id == customer_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_customer_portfolio_summary(
        db: Session,
        customer_id: uuid.UUID,
    ) -> dict:
        """Calculate customer's portfolio summary, asset allocations, and net worth."""
        investments_stmt = (
            select(Investment)
            .join(FinancialProduct, Investment.product_id == FinancialProduct.id)
            .where(Investment.customer_id == customer_id, Investment.status == "ACTIVE")
            .order_by(Investment.created_at.desc())
        )
        active_investments = list(db.scalars(investments_stmt).all())

        # Customer liquid savings / current balances
        accounts_stmt = select(Account).where(
            Account.customer_id == customer_id,
            Account.status == "ACTIVE",
            Account.account_type.in_(["SAVINGS", "CURRENT"]),
        )
        liquid_accounts = list(db.scalars(accounts_stmt).all())
        available_savings = sum((acc.cached_balance for acc in liquid_accounts), Decimal("0.00"))

        total_invested = Decimal("0.00")
        total_current_val = Decimal("0.00")
        allocation_by_type: dict[str, Decimal] = {}
        holdings_items = []

        now_utc = datetime.now(timezone.utc)

        for inv in active_investments:
            total_invested += inv.invested_amount
            total_current_val += inv.current_value

            prod = inv.product
            ptype = prod.product_type if prod else "OTHER"
            allocation_by_type[ptype] = allocation_by_type.get(ptype, Decimal("0.00")) + inv.invested_amount

            # Calculate nominal accrued yield: principal * (rate / 100) * (days / 365)
            elapsed_days = max(0, (now_utc - inv.start_date).days)
            yield_rate = prod.annual_yield_rate if prod else Decimal("0.00")
            nominal_yield = (
                inv.invested_amount * (yield_rate / Decimal("100.00")) * (Decimal(elapsed_days) / Decimal("365.00"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

            holdings_items.append({
                "investment_id": inv.id,
                "product_name": prod.name if prod else "Unknown",
                "product_code": prod.code if prod else "UNKNOWN",
                "product_type": ptype,
                "annual_yield_rate": yield_rate,
                "invested_amount": inv.invested_amount,
                "current_value": inv.current_value,
                "status": inv.status,
                "start_date": inv.start_date,
                "maturity_date": inv.maturity_date,
                "term_months": prod.term_months if prod else 0,
                "nominal_accrued_yield": nominal_yield,
            })

        return {
            "customer_id": customer_id,
            "total_invested": total_invested,
            "total_current_value": total_current_val,
            "active_investments_count": len(active_investments),
            "available_savings_balance": available_savings,
            "total_net_worth": available_savings + total_invested,
            "allocation_by_product_type": allocation_by_type,
            "holdings": holdings_items,
        }
