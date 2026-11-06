from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InventoryItemCreate(BaseModel):
    product_id: str
    sku: str
    available_quantity: int = Field(ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)


class InventoryStockAdjust(BaseModel):
    adjustment: int = Field(description="Positive to add, negative to subtract")
    reason: str = Field(min_length=3)


class InventoryItemResponse(BaseModel):
    product_id: str
    sku: str
    available_quantity: int
    reserved_quantity: int
    sold_quantity: int
    total_quantity: int
    low_stock_threshold: int
    updated_at: datetime


class ReserveItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class ReserveStockRequest(BaseModel):
    order_id: str
    items: List[ReserveItemRequest]

