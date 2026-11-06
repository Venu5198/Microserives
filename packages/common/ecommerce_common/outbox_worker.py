import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from ecommerce_common.database import resolve_db
from ecommerce_common.rabbitmq import RabbitMQClient

logger = logging.getLogger("outbox-worker")


class OutboxWorker:
    def __init__(
        self,
        db_manager: Any,
        rabbitmq_client: RabbitMQClient,
        poll_interval: float = 1.0,
        batch_size: int = 50,
        max_retries: int = 5,
    ):
        self.db_manager = db_manager
        self.db = resolve_db(db_manager)
        self.rabbitmq_client = rabbitmq_client
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Outbox worker started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Outbox worker stopped")

    async def _run_loop(self):
        while self._running:
            try:
                await self._process_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Outbox worker iteration error: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    async def _process_batch(self):
        target_db = self.db if self.db is not None else resolve_db(self.db_manager)
        if target_db is None:
            return

        cursor = (
            target_db.outbox.find({"status": "PENDING"})
            .sort("created_at", 1)
            .limit(self.batch_size)
        )

        messages = await cursor.to_list(length=self.batch_size)
        if not messages:
            return

        for msg in messages:
            outbox_id = msg.get("outbox_id")
            event_type = msg.get("event_type")
            routing_key = f"{msg.get('producer', 'system')}.{event_type}"

            envelope = {
                "event_id": msg.get("outbox_id"),
                "event_type": event_type,
                "event_version": 1,
                "aggregate_id": msg.get("aggregate_id"),
                "correlation_id": msg.get("correlation_id"),
                "occurred_at": msg.get("created_at").isoformat()
                if isinstance(msg.get("created_at"), datetime)
                else str(msg.get("created_at")),
                "producer": msg.get("producer"),
                "payload": msg.get("payload", {}),
            }

            try:
                await self.rabbitmq_client.publish_event(
                    routing_key=routing_key,
                    envelope=envelope,
                )
                await target_db.outbox.update_one(
                    {"_id": msg["_id"]},
                    {
                        "$set": {
                            "status": "PUBLISHED",
                            "published_at": datetime.now(UTC),
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
            except Exception as ex:
                retry_count = msg.get("retry_count", 0) + 1
                new_status = "FAILED" if retry_count >= self.max_retries else "PENDING"
                logger.warning(
                    f"Failed to publish outbox event {outbox_id} (attempt {retry_count}): {ex}"
                )
                await target_db.outbox.update_one(
                    {"_id": msg["_id"]},
                    {
                        "$set": {
                            "status": new_status,
                            "retry_count": retry_count,
                            "last_error": str(ex),
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
