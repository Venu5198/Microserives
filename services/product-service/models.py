from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str
    price: int = Field(gt=0, description="Price in minor units (cents)")
    category: str
    sku: str = Field(min_length=2, max_length=50)
    image_url: str | None = (
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&auto=format&fit=crop&q=60"
    )
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: int | None = Field(default=None, gt=0)
    category: str | None = None
    image_url: str | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    price: int
    category: str
    sku: str
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
