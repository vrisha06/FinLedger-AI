"""Pydantic v2 schemas for Financial Reporting & Analytics."""

from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel


class CustomerFinancialSummaryResponse(BaseModel):
    """Customer-level financial summary."""

    customer_id: uuid.UUID
    customer_name: str
    accounts_count: int
    total_savings_balance: Decimal
    total_invested_balance: Decimal
    total_net_worth: Decimal
    total_transfers_sent_count: int
    total_transfers_sent_volume: Decimal
    total_transfers_received_count: int
    total_transfers_received_volume: Decimal
    active_investments_count: int


class ProductSummaryItem(BaseModel):
    """Staff-level aggregation for a financial product."""

    product_id: uuid.UUID
    name: str
    code: str
    product_type: str
    annual_yield_rate: Decimal
    min_amount: Decimal
    term_months: int
    is_active: bool
    total_subscriptions: int
    active_subscriptions: int
    total_invested_volume: Decimal


class ProductsSummaryResponse(BaseModel):
    """Staff-level product catalogue performance report."""

    timestamp: datetime
    products: list[ProductSummaryItem]
    total_products_count: int
    total_system_invested_volume: Decimal


class DailyVolumeItem(BaseModel):
    """Daily transactional and investment volume record."""

    date: str
    transfer_count: int
    transfer_volume: Decimal
    investment_count: int
    investment_volume: Decimal
    total_day_volume: Decimal


class DailyVolumeResponse(BaseModel):
    """Aggregated daily activity metrics."""

    timestamp: datetime
    daily_records: list[DailyVolumeItem]


class BalanceDistributionResponse(BaseModel):
    """System-wide account balance tier distributions."""

    timestamp: datetime
    total_accounts: int
    system_clearing_balance: Decimal
    total_customer_liabilities: Decimal
    tier_under_1k_count: int
    tier_1k_to_10k_count: int
    tier_10k_to_50k_count: int
    tier_50k_to_100k_count: int
    tier_above_100k_count: int
