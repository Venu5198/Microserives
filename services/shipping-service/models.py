from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShipmentStatus(str, Enum):
    CREATED = "CREATED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    RETURNED = "RETURNED"


class TrackingEventResponse(BaseModel):
    status: str
    location: str
    description: str
    timestamp: datetime


class ShipmentStatusUpdateRequest(BaseModel):
    status: ShipmentStatus
    location: str = "Regional Sorting Facility"
    notes: Optional[str] = "Package in transit"


class ShipmentResponse(BaseModel):
    id: str
    order_id: str
    tracking_number: str
    carrier: str
    status: ShipmentStatus
    estimated_delivery: datetime
    shipping_address: Dict[str, Any]
    events: List[TrackingEventResponse] = []
    created_at: datetime
    updated_at: datetime

