"""FastAPI router for Financial Product Catalogue endpoints."""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_staff
from app.models.user import User
from app.schemas.product import ProductCreateRequest, ProductResponse
from app.services.product_service import ProductService, ProductConflictError

router = APIRouter(prefix="/products", tags=["Financial Products"])


@router.get("", response_model=List[ProductResponse])
def list_products(
    product_type: Optional[str] = Query(None, description="Filter by product category"),
    is_active: Optional[bool] = Query(True, description="Filter by active status (default: True)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieve list of simulated financial products in the catalogue."""
    return ProductService.list_products(
        db=db,
        product_type=product_type,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.get("/{id}", response_model=ProductResponse)
def get_product(
    id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve details for a specific financial product."""
    product = ProductService.get_product_by_id(db, id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Financial product with ID '{id}' not found",
        )
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Create a new financial product in the catalogue (staff only)."""
    try:
        return ProductService.create_product(
            db=db,
            product_in=payload,
            actor_user_id=current_user.id,
        )
    except ProductConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
