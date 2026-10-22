"""Aggregated API v1 router."""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.transfers import router as transfers_router
from app.api.v1.audit import router as audit_router
from app.api.v1.fraud import router as fraud_router
from app.api.v1.products import router as products_router
from app.api.v1.investments import router as investments_router
from app.api.v1.reports import router as reports_router
from app.api.v1.graph import router as graph_router
from app.api.v1.disputes import router as disputes_router
from app.api.v1.fraud_lab import router as fraud_lab_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(accounts_router)
api_router.include_router(transfers_router)
api_router.include_router(audit_router)
api_router.include_router(fraud_router)
api_router.include_router(products_router)
api_router.include_router(investments_router)
api_router.include_router(reports_router)
api_router.include_router(graph_router)
api_router.include_router(disputes_router)
api_router.include_router(fraud_lab_router)
