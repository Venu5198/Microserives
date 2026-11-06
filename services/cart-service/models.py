from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CartItemAdd(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, default=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemResponse(BaseModel):
    product_id: str
    product_name: str
    unit_price: int  # in minor units (cents)
    quantity: int
    image_url: Optional[str] = None
    subtotal: int


class CartResponse(BaseModel):
    user_id: str
    items: List[CartItemResponse] = []
    total_amount: int
    total_items: int
    updated_at: datetime
