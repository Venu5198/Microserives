from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, EmailStr


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationSendRequest(BaseModel):
    recipient_email: str
    recipient_name: Optional[str] = "Customer"
    subject: str
    template_name: str
    template_data: Dict[str, Any] = {}


class NotificationResponse(BaseModel):
    id: str
    recipient_email: str
    subject: str
    template_name: str
    status: str  # SENT, FAILED, RETRYING
    attempt_count: int
    content: str
    error: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

