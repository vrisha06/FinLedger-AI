"""Financial Reporting and Analytics Service for FinLedger-AI.

Generates authoritative customer summaries, product performance metrics,
daily volume trends, and account balance tier distributions.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.account import Account
from app.models.product import FinancialProduct, Investment
from app.models.transfer import TransferRequest


class ReportService:
    """Service providing database-backed financial summaries and staff analytics."""

    @staticmethod
    def get_customer_financial_summary(db: Session, customer_id: uuid.UUID) -> dict:
        """Aggregate comprehensive financial standing for an individual customer."""
        customer = db.get(Customer, customer_id)
        if not customer:
            raise ValueError(f"Customer with ID {customer_id} not found")

        # 1. Accounts & balances
        accounts_stmt = select(Account).where(
            Account.customer_id == customer_id,
            Account.status == "ACTIVE",
        )
        accounts = list(db.scalars(accounts_stmt).all())

        total_savings = Decimal("0.00")
        total_invested_balance = Decimal("0.00")

        for acc in accounts:
            if acc.account_type in ("SAVINGS", "CURRENT"):
                total_savings += acc.cached_balance
            elif acc.account_type == "INVESTMENT":
                total_invested_balance += acc.cached_balance

        # 2. Transfers sent
        sent_stmt = select(
            func.count(TransferRequest.id),
            func.coalesce(func.sum(TransferRequest.amount), Decimal("0.00")),
        ).where(
            TransferRequest.source_user_id == customer.user_id,
            TransferRequest.status == "POSTED",
        )
        sent_count, sent_vol = db.execute(sent_stmt).one()

        # 3. Transfers received (where destination account belongs to customer, excluding self transfers)
        cust_acc_ids = [acc.id for acc in accounts]
        received_count = 0
        received_vol = Decimal("0.00")
        if cust_acc_ids:
            recv_stmt = select(
                func.count(TransferRequest.id),
                func.coalesce(func.sum(TransferRequest.amount), Decimal("0.00")),
            ).where(
                TransferRequest.destination_account_id.in_(cust_acc_ids),
                TransferRequest.source_user_id != customer.user_id,
                TransferRequest.status == "POSTED",
            )
            received_count, received_vol = db.execute(recv_stmt).one()

        # 4. Active investments count
        inv_stmt = select(func.count(Investment.id)).where(
            Investment.customer_id == customer_id,
            Investment.status == "ACTIVE",
        )
        active_inv_count = db.scalar(inv_stmt) or 0

        return {
            "customer_id": customer.id,
            "customer_name": customer.full_name,
            "accounts_count": len(accounts),
            "total_savings_balance": total_savings,
            "total_invested_balance": total_invested_balance,
            "total_net_worth": total_savings + total_invested_balance,
            "total_transfers_sent_count": sent_count,
            "total_transfers_sent_volume": sent_vol,
            "total_transfers_received_count": received_count,
            "total_transfers_received_volume": received_vol,
            "active_investments_count": active_inv_count,
        }

    @staticmethod
    def get_products_summary(db: Session) -> dict:
        """Generate staff aggregate summary across all financial products."""
        products_stmt = select(FinancialProduct).order_by(FinancialProduct.product_type.asc(), FinancialProduct.name.asc())
        products = list(db.scalars(products_stmt).all())

        product_items = []
        total_system_invested = Decimal("0.00")

        for prod in products:
            stats_stmt = select(
                func.count(Investment.id),
                func.coalesce(func.sum(case((Investment.status == "ACTIVE", 1), else_=0)), 0),
                func.coalesce(func.sum(Investment.invested_amount), Decimal("0.00")),
            ).where(Investment.product_id == prod.id)

            total_subs, active_subs, total_vol = db.execute(stats_stmt).one()
            total_system_invested += total_vol

            product_items.append({
                "product_id": prod.id,
                "name": prod.name,
                "code": prod.code,
                "product_type": prod.product_type,
                "annual_yield_rate": prod.annual_yield_rate,
                "min_amount": prod.min_amount,
                "term_months": prod.term_months,
                "is_active": prod.is_active,
                "total_subscriptions": total_subs,
                "active_subscriptions": active_subs,
                "total_invested_volume": total_vol,
            })

        return {
            "timestamp": datetime.now(timezone.utc),
            "products": product_items,
            "total_products_count": len(products),
            "total_system_invested_volume": total_system_invested,
        }

    @staticmethod
    def get_daily_volume(db: Session, days: int = 14) -> dict:
        """Aggregate daily transactional and investment volumes for the last N days."""
        now_utc = datetime.now(timezone.utc)
        today_utc = now_utc.date()
        start_date = today_utc - timedelta(days=days)
        start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

        # 1. Daily transfers
        transfers_stmt = (
            select(
                func.to_char(func.timezone("UTC", TransferRequest.posted_at), "YYYY-MM-DD").label("day"),
                func.count(TransferRequest.id).label("count"),
                func.coalesce(func.sum(TransferRequest.amount), Decimal("0.00")).label("volume"),
            )
            .where(TransferRequest.status == "POSTED", TransferRequest.posted_at >= start_datetime)
            .group_by("day")
            .order_by("day")
        )
        transfers_by_day = {r.day: (r.count, r.volume) for r in db.execute(transfers_stmt).all()}

        # 2. Daily investments
        investments_stmt = (
            select(
                func.to_char(func.timezone("UTC", Investment.created_at), "YYYY-MM-DD").label("day"),
                func.count(Investment.id).label("count"),
                func.coalesce(func.sum(Investment.invested_amount), Decimal("0.00")).label("volume"),
            )
            .where(Investment.created_at >= start_datetime)
            .group_by("day")
            .order_by("day")
        )
        investments_by_day = {r.day: (r.count, r.volume) for r in db.execute(investments_stmt).all()}

        # Construct records for every date in range
        records = []
        for d in range(days + 1):
            curr_date_str = (start_date + timedelta(days=d)).isoformat()
            t_count, t_vol = transfers_by_day.get(curr_date_str, (0, Decimal("0.00")))
            i_count, i_vol = investments_by_day.get(curr_date_str, (0, Decimal("0.00")))
            records.append({
                "date": curr_date_str,
                "transfer_count": t_count,
                "transfer_volume": t_vol,
                "investment_count": i_count,
                "investment_volume": i_vol,
                "total_day_volume": t_vol + i_vol,
            })

        return {
            "timestamp": datetime.now(timezone.utc),
            "daily_records": records,
        }

    @staticmethod
    def get_balance_distribution(db: Session) -> dict:
        """Calculate distribution of account balances across standard financial tiers."""
        accounts = list(db.scalars(select(Account)).all())

        tier_under_1k = 0
        tier_1k_to_10k = 0
        tier_10k_to_50k = 0
        tier_50k_to_100k = 0
        tier_above_100k = 0
        clearing_bal = Decimal("0.00")
        cust_liabilities = Decimal("0.00")

        for acc in accounts:
            if acc.account_type == "INTERNAL_CLEARING":
                clearing_bal += acc.cached_balance
            else:
                cust_liabilities += acc.cached_balance
                bal = acc.cached_balance
                if bal < Decimal("1000.00"):
                    tier_under_1k += 1
                elif bal < Decimal("10000.00"):
                    tier_1k_to_10k += 1
                elif bal < Decimal("50000.00"):
                    tier_10k_to_50k += 1
                elif bal < Decimal("100000.00"):
                    tier_50k_to_100k += 1
                else:
                    tier_above_100k += 1

        return {
            "timestamp": datetime.now(timezone.utc),
            "total_accounts": len(accounts),
            "system_clearing_balance": clearing_bal,
            "total_customer_liabilities": cust_liabilities,
            "tier_under_1k_count": tier_under_1k,
            "tier_1k_to_10k_count": tier_1k_to_10k,
            "tier_10k_to_50k_count": tier_10k_to_50k,
            "tier_50k_to_100k_count": tier_50k_to_100k,
            "tier_above_100k_count": tier_above_100k,
        }
