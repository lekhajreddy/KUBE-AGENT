"""
KubeMind — Redis Event Bus
Pub/sub event bus for real-time telemetry streaming between agents, backend, and dashboard clients.
"""
import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, Optional

from app.core.config import settings

logger = logging.getLogger("kubemind.eventbus")

_redis = None
_kafka_producer = None
_kafka_consumers = []
_listeners: Dict[str, list] = {}

async def init_event_bus():
    """Initialize Redis/Kafka connections for pub/sub."""
    await init_redis()
    await init_kafka()

async def close_event_bus():
    await close_redis()
    await close_kafka()

async def init_redis():
    global _redis
    if not settings.REDIS_ENABLED:
        return
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
        await _redis.ping()
        logger.info(f"✅ Redis event bus connected: {settings.REDIS_URL}")
    except Exception as e:
        logger.warning(f"Redis connection failed — running without pub/sub: {e}")
        _redis = None

async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None

async def init_kafka():
    global _kafka_producer
    kafka_brokers = os.environ.get("KAFKA_BROKERS")
    if not kafka_brokers:
        return
    try:
        from aiokafka import AIOKafkaProducer
        _kafka_producer = AIOKafkaProducer(bootstrap_servers=kafka_brokers)
        await _kafka_producer.start()
        logger.info(f"✅ Kafka producer connected: {kafka_brokers}")
    except Exception as e:
        logger.warning(f"Kafka connection failed: {e}")
        _kafka_producer = None

async def close_kafka():
    global _kafka_producer
    if _kafka_producer:
        await _kafka_producer.stop()
        _kafka_producer = None
    for consumer in _kafka_consumers:
        await consumer.stop()
    _kafka_consumers.clear()

def _channel(prefix: str, cluster_id: str = "default") -> str:
    return f"kubemind:{prefix}:{cluster_id}"

async def publish(channel_prefix: str, data: Dict[str, Any], cluster_id: str = "default"):
    channel = _channel(channel_prefix, cluster_id)
    payload = json.dumps(data, default=str)

    # Local listeners
    for cb in _listeners.get(channel, []):
        try:
            asyncio.create_task(cb(data))
        except Exception as e:
            logger.error(f"Local listener error on {channel}: {e}")

    if _redis:
        try:
            await _redis.publish(channel, payload)
        except Exception as e:
            logger.warning(f"Redis publish error on {channel}: {e}")

    if _kafka_producer:
        try:
            await _kafka_producer.send_and_wait(channel_prefix, payload.encode("utf-8"), key=cluster_id.encode("utf-8"))
        except Exception as e:
            logger.warning(f"Kafka publish error on {channel}: {e}")


# ── Subscribe (local in-process) ──────────────────────────────────────────────
def subscribe_local(channel_prefix: str, callback: Callable, cluster_id: str = "default"):
    """Register a local in-process listener for a channel."""
    channel = _channel(channel_prefix, cluster_id)
    _listeners.setdefault(channel, []).append(callback)
    logger.debug(f"Local subscriber added for {channel}")


def unsubscribe_local(channel_prefix: str, callback: Callable, cluster_id: str = "default"):
    channel = _channel(channel_prefix, cluster_id)
    if channel in _listeners:
        _listeners[channel] = [cb for cb in _listeners[channel] if cb != callback]


# ── Subscribe (Redis pub/sub) ─────────────────────────────────────────────────
async def subscribe_redis(channel_prefix: str, callback: Callable, cluster_id: str = "default"):
    """Subscribe to Redis pub/sub channel. Runs forever — call in background task."""
    if not _redis:
        logger.warning("Redis not available — cannot subscribe")
        return

    channel = _channel(channel_prefix, cluster_id)
    pubsub = _redis.pubsub()
    await pubsub.subscribe(channel)
    logger.info(f"Subscribed to Redis channel: {channel}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await callback(data)
                except Exception as e:
                    logger.error(f"Redis subscriber callback error: {e}")
    except asyncio.CancelledError:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


# ── Convenience publishers ────────────────────────────────────────────────────
async def publish_metrics(metrics: Dict, cluster_id: str = "default"):
    await publish("metrics", metrics, cluster_id)


async def publish_anomaly(anomaly: Dict, cluster_id: str = "default"):
    await publish("anomalies", anomaly, cluster_id)


async def publish_alert(alert: Dict, cluster_id: str = "default"):
    await publish("alerts", alert, cluster_id)


async def publish_topology(topology: Dict, cluster_id: str = "default"):
    await publish("topology", topology, cluster_id)


async def publish_agent_heartbeat(cluster_id: str, agent_info: Dict):
    await publish("agent", {"type": "heartbeat", **agent_info}, cluster_id)
