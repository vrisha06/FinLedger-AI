"""FinLedger-AI API Schemas."""

from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    CustomerProfileResponse,
)
from app.schemas.audit import AuditLogResponse
from app.schemas.account import AccountResponse, DepositRequest
from app.schemas.transfer import TransferCreateRequest, TransferResponse
from app.schemas.ledger import LedgerEntryResponse, ReconciliationReport, DiscrepancyItem
from app.schemas.fraud import FraudPredictionResponse, FraudAlertReviewRequest
from app.schemas.product import ProductCreateRequest, ProductResponse
from app.schemas.investment import (
    InvestmentCreateRequest,
    InvestmentResponse,
    PortfolioHoldingItem,
    PortfolioSummaryResponse,
)
from app.schemas.report import (
    CustomerFinancialSummaryResponse,
    ProductSummaryItem,
    ProductsSummaryResponse,
    DailyVolumeItem,
    DailyVolumeResponse,
    BalanceDistributionResponse,
)

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "CustomerProfileResponse",
    "AuditLogResponse",
    "AccountResponse",
    "DepositRequest",
    "TransferCreateRequest",
    "TransferResponse",
    "LedgerEntryResponse",
    "ReconciliationReport",
    "DiscrepancyItem",
    "FraudPredictionResponse",
    "FraudAlertReviewRequest",
    "ProductCreateRequest",
    "ProductResponse",
    "InvestmentCreateRequest",
    "InvestmentResponse",
    "PortfolioHoldingItem",
    "PortfolioSummaryResponse",
    "CustomerFinancialSummaryResponse",
    "ProductSummaryItem",
    "ProductsSummaryResponse",
    "DailyVolumeItem",
    "DailyVolumeResponse",
    "BalanceDistributionResponse",
]
