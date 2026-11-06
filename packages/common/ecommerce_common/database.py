import uuid
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    res = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            res[k] = str(v)
        elif isinstance(v, datetime):
            res[k] = v.isoformat()
        elif isinstance(v, list):
            res[k] = [
                serialize_doc(item)
                if isinstance(item, dict)
                else (str(item) if isinstance(item, ObjectId) else item)
                for item in v
            ]
        elif isinstance(v, dict):
            res[k] = serialize_doc(v)
        else:
            res[k] = v
    if "_id" in res and "id" not in res:
        res["id"] = res.pop("_id")
    return res


class DatabaseManager:
    def __init__(self, mongo_uri: str, db_name: str):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    async def connect(self):
        self.client = AsyncIOMotorClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        return self.db

    async def disconnect(self):
        if self.client:
            self.client.close()

    async def create_outbox_message(
        self,
        event_type: str,
        aggregate_id: str,
        correlation_id: str,
        producer: str,
        payload: dict[str, Any],
        session=None,
    ) -> dict[str, Any]:
        """
        Inserts an event into the outbox collection for guaranteed delivery.
        Can run inside an existing MongoDB transaction session if replica set is active.
        """
        now = datetime.now(UTC)
        message = {
            "outbox_id": str(uuid.uuid4()),
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "correlation_id": correlation_id,
            "producer": producer,
            "payload": payload,
            "status": "PENDING",  # PENDING, PUBLISHED, FAILED
            "retry_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        await self.db.outbox.insert_one(message, session=session)
        return message
