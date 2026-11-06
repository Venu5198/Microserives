from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class NotificationSendRequest(BaseModel):
    recipient_email: str
    recipient_name: str | None = "Customer"
    subject: str
    template_name: str
    template_data: dict[str, Any] = {}


class NotificationResponse(BaseModel):
    id: str
    recipient_email: str
    subject: str
    template_name: str
    status: str  # SENT, FAILED, RETRYING
    attempt_count: int
    content: str
    error: str | None = None
    created_at: datetime
    sent_at: datetime | None = None
