"""
KubeMind — Kubernetes Event Processing Pipeline
Ingests K8s events, enriches them, and streams to Redis + WebSocket.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable

from backend.services.kube.client import get_core_v1

logger = logging.getLogger("kubemind.kube.events")

EVENT_PRIORITIES = {
    "CrashLoopBackOff": 0,
    "OOMKilled": 1,
    "NodeNotReady": 2,
    "BackOff": 3,
    "ImagePullBackOff": 4,
    "Failed": 5,
    "FailedScheduling": 6,
    "Unhealthy": 7,
    "ProbeWarning": 8,
    "Evicted": 9,
}


class EventProcessor:
    def __init__(self):
        self._event_cache: Dict[str, List[dict]] = {}
        self._listeners: List[Callable] = []

    def register_listener(self, callback: Callable):
        self._listeners.append(callback)

    async def process_event(self, event: dict) -> Optional[dict]:
        enriched = self._enrich(event)
        if enriched:
            svc = enriched.get("involved_object", "")
            ns = enriched.get("namespace", "")
            key = f"{ns}/{svc}"
            if key not in self._event_cache:
                self._event_cache[key] = []
            self._event_cache[key].append(enriched)
            if len(self._event_cache[key]) > 100:
                self._event_cache[key].pop(0)
            for listener in self._listeners:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(enriched)
                    else:
                        listener(enriched)
                except Exception as e:
                    logger.error(f"Event listener error: {e}")
            return enriched
        return None

    def _enrich(self, event: dict) -> Optional[dict]:
        reason = event.get("reason", "")
        message = event.get("message", "")
        involved = event.get("involved_object", "")
        kind = event.get("involved_kind", "")
        ns = event.get("namespace", "")
        if not reason and not message:
            return None
        priority = EVENT_PRIORITIES.get(reason, 99)
        event_type = "critical" if priority <= 1 else "warning" if priority <= 5 else "info"
        return {
            "id": f"{ns}/{involved}/{reason}/{datetime.now(timezone.utc).timestamp()}",
            "namespace": ns,
            "involved_object": involved,
            "involved_kind": kind,
            "reason": reason,
            "message": message,
            "priority": priority,
            "event_type": event_type,
            "count": event.get("count", 1),
            "first_time": event.get("first_time", ""),
            "last_time": event.get("last_time", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_recent_events(self, limit: int = 50) -> List[dict]:
        all_events = []
        for evts in self._event_cache.values():
            all_events.extend(evts)
        all_events.sort(key=lambda e: e.get("priority", 99))
        return all_events[:limit]

    def get_pod_events(self, namespace: str, pod: str) -> List[dict]:
        key = f"{namespace}/{pod}"
        return self._event_cache.get(key, [])[-20:]


event_processor = EventProcessor()
