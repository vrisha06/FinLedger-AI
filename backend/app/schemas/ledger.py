"""Ledger and reconciliation Pydantic v2 schemas for FinLedger-AI."""

from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict


class LedgerEntryResponse(BaseModel):
    """Immutable ledger entry posting leg."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    account_id: uuid.UUID
    entry_type: str
    amount: Decimal
    sequence_num: int
    created_at: datetime


class DiscrepancyItem(BaseModel):
    """Account reconciliation mismatch record."""

    account_id: uuid.UUID
    account_number: str
    cached_balance: Decimal
    derived_balance: Decimal
    discrepancy: Decimal


class ReconciliationReport(BaseModel):
    """System-wide ledger balance reconciliation audit report."""

    reconciled_at: datetime
    total_accounts_checked: int
    discrepancy_count: int
    is_balanced: bool
    system_clearing_balance: Decimal
    total_customer_liabilities: Decimal
    global_net_ledger_delta: Decimal
    discrepancies: list[DiscrepancyItem]
