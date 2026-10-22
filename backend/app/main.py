"""FinLedger-AI FastAPI Application Entry Point.

Configures REST API routing, middleware, CORS, health endpoints,
and sanitized exception handlers to protect sensitive internals.
"""

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings

logger = logging.getLogger("finledger")

app = FastAPI(
    title="FinLedger-AI API",
    version="1.0.0",
    description="Auditable Financial Transaction System with AI-Assisted Fraud Detection",
    docs_url=f"{settings.API_V1_PREFIX}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_PREFIX}/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health & System Status"])
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "FinLedger-AI",
        "environment": settings.ENVIRONMENT,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevent unhandled internal exceptions or database errors from leaking raw traces."""
    logger.error("Unhandled internal server error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Please try again later."},
    )
