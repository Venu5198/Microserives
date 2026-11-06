import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional
import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode

logger = logging.getLogger("rabbitmq-client")


class RabbitMQClient:
    def __init__(
        self,
        rabbitmq_url: str,
        exchange_name: str = "ecommerce.events",
        dlx_exchange_name: str = "ecommerce.dlx",
    ):
        self.rabbitmq_url = rabbitmq_url
        self.exchange_name = exchange_name
        self.dlx_exchange_name = dlx_exchange_name
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None
        self.exchange: Optional[aio_pika.RobustExchange] = None
        self.dlx_exchange: Optional[aio_pika.RobustExchange] = None

    async def connect(self):
        retries = 5
        delay = 2
        for attempt in range(1, retries + 1):
            try:
                self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=10)

                # Declare Dead Letter Exchange
                self.dlx_exchange = await self.channel.declare_exchange(
                    self.dlx_exchange_name,
                    ExchangeType.TOPIC,
                    durable=True,
                )

                # Declare Main Exchange
                self.exchange = await self.channel.declare_exchange(
                    self.exchange_name,
                    ExchangeType.TOPIC,
                    durable=True,
                )
                logger.info(f"Connected to RabbitMQ and declared exchanges: {self.exchange_name}, {self.dlx_exchange_name}")
                return
            except Exception as e:
                logger.warning(f"RabbitMQ connection attempt {attempt} failed: {e}")
                if attempt == retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

    async def publish_event(
        self,
        routing_key: str,
        envelope: Dict[str, Any],
        headers: Optional[Dict[str, Any]] = None,
    ):
        if not self.exchange:
            raise RuntimeError("RabbitMQ exchange not initialized")

        body = json.dumps(envelope).encode("utf-8")
        msg_headers = headers or {}
        msg_headers["correlation_id"] = envelope.get("correlation_id", "")
        msg_headers["event_type"] = envelope.get("event_type", "")

        message = Message(
            body=body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=msg_headers,
            message_id=envelope.get("event_id"),
            correlation_id=envelope.get("correlation_id"),
        )
        await self.exchange.publish(message, routing_key=routing_key)

    async def register_consumer(
        self,
        queue_name: str,
        routing_keys: list[str],
        message_handler: Callable[[Dict[str, Any]], Any],
        max_retries: int = 3,
    ):
        """
        Creates a durable queue bound to routing keys with dead letter configuration,
        and starts an asynchronous consumer loop with manual ack/nack.
        """
        if not self.channel or not self.exchange:
            raise RuntimeError("RabbitMQ channel not initialized")

        dlq_name = f"{queue_name}.dlq"
        # Declare DLQ queue and bind to DLX
        dlq = await self.channel.declare_queue(dlq_name, durable=True)
        for rk in routing_keys:
            await dlq.bind(self.dlx_exchange, routing_key=rk)

        # Declare main queue with DLX forwarding on reject
        queue = await self.channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.dlx_exchange_name,
            },
        )
        for rk in routing_keys:
            await queue.bind(self.exchange, routing_key=rk)

        async def _consumer():
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process(requeue=False, ignore_processed=True):
                        try:
                            payload_data = json.loads(message.body.decode("utf-8"))
                            await message_handler(payload_data)
                            await message.ack()
                        except Exception as ex:
                            logger.error(
                                f"Error processing message in {queue_name}: {ex}. Routing to DLQ.",
                                exc_info=True,
                            )
                            # Reject without requeue will automatically route to DLX
                            await message.reject(requeue=False)

        asyncio.create_task(_consumer())
        logger.info(f"Consumer started on queue: {queue_name} for keys: {routing_keys}")
