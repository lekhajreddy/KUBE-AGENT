"""
KubeMind — Kubernetes Watch API with Redis Stream Pipeline
Real-time event streaming from K8s to Redis Streams to WebSocket.
"""
import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional

from kubernetes import client, watch
from kubernetes.client.rest import ApiException

from backend.services.kube.client import get_core_v1, get_apps_v1

logger = logging.getLogger("kubemind.kube.watchers")

_REDIS_STREAM_MAXLEN = 10000


class K8sWatcher:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def start_all(self):
        self._running = True
        self._tasks["pods"] = asyncio.create_task(self._watch_pods())
        self._tasks["services"] = asyncio.create_task(self._watch_services())
        self._tasks["deployments"] = asyncio.create_task(self._watch_deployments())
        self._tasks["events"] = asyncio.create_task(self._watch_events())
        self._tasks["nodes"] = asyncio.create_task(self._watch_nodes())
        logger.info("All K8s watchers started")

    async def stop_all(self):
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("All K8s watchers stopped")

    async def _publish(self, stream: str, data: dict):
        if self._redis:
            try:
                await self._redis.xadd(
                    f"kubemind:{stream}",
                    {"data": json.dumps(data, default=str)},
                    maxlen=_REDIS_STREAM_MAXLEN,
                )
            except Exception as e:
                logger.debug(f"Redis xadd failed: {e}")

    async def _watch_pods(self):
        v1 = get_core_v1()
        if not v1:
            return
        w = watch.Watch()
        while self._running:
            try:
                for event in w.stream(v1.list_pod_for_all_namespaces, timeout_seconds=60):
                    if not self._running:
                        break
                    obj = event["object"]
                    pod_data = {
                        "type": event["type"],
                        "pod": obj.metadata.name,
                        "namespace": obj.metadata.namespace,
                        "node": obj.spec.node_name or "",
                        "status": obj.status.phase or "",
                        "container_statuses": [
                            {
                                "name": cs.name,
                                "ready": cs.ready,
                                "restart_count": cs.restart_count or 0,
                                "state": self._container_state(cs.state),
                            }
                            for cs in (obj.status.container_statuses or [])
                        ],
                        "labels": obj.metadata.labels or {},
                        "creation_timestamp": str(obj.metadata.creation_timestamp),
                        "deletion_timestamp": str(obj.metadata.deletion_timestamp) if obj.metadata.deletion_timestamp else None,
                    }
                    await self._publish("pods", pod_data)
            except ApiException as e:
                logger.warning(f"Pod watch error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Pod watch unexpected: {e}")
                await asyncio.sleep(10)

    async def _watch_services(self):
        v1 = get_core_v1()
        if not v1:
            return
        w = watch.Watch()
        while self._running:
            try:
                for event in w.stream(v1.list_service_for_all_namespaces, timeout_seconds=60):
                    if not self._running:
                        break
                    obj = event["object"]
                    svc_data = {
                        "type": event["type"],
                        "service": obj.metadata.name,
                        "namespace": obj.metadata.namespace,
                        "type": obj.spec.type or "ClusterIP",
                        "cluster_ip": obj.spec.cluster_ip or "",
                        "ports": [
                            {"port": p.port, "target_port": str(p.target_port or ""), "protocol": p.protocol or ""}
                            for p in (obj.spec.ports or [])
                        ],
                        "selector": obj.spec.selector or {},
                        "labels": obj.metadata.labels or {},
                    }
                    await self._publish("services", svc_data)
            except ApiException as e:
                logger.warning(f"Service watch error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Service watch unexpected: {e}")
                await asyncio.sleep(10)

    async def _watch_deployments(self):
        apps = get_apps_v1()
        if not apps:
            return
        w = watch.Watch()
        while self._running:
            try:
                for event in w.stream(apps.list_deployment_for_all_namespaces, timeout_seconds=60):
                    if not self._running:
                        break
                    obj = event["object"]
                    dep_data = {
                        "type": event["type"],
                        "deployment": obj.metadata.name,
                        "namespace": obj.metadata.namespace,
                        "replicas": obj.spec.replicas or 0,
                        "ready_replicas": obj.status.ready_replicas or 0,
                        "available_replicas": obj.status.available_replicas or 0,
                        "selector": obj.spec.selector.match_labels if obj.spec.selector else {},
                        "labels": obj.metadata.labels or {},
                    }
                    await self._publish("deployments", dep_data)
            except ApiException as e:
                logger.warning(f"Deployment watch error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Deployment watch unexpected: {e}")
                await asyncio.sleep(10)

    async def _watch_events(self):
        v1 = get_core_v1()
        if not v1:
            return
        w = watch.Watch()
        while self._running:
            try:
                for event in w.stream(v1.list_event_for_all_namespaces, timeout_seconds=60):
                    if not self._running:
                        break
                    obj = event["object"]
                    if obj.type != "Warning":
                        continue
                    ev_data = {
                        "type": "EVENT",
                        "event_type": obj.type or "",
                        "reason": obj.reason or "",
                        "message": obj.message or "",
                        "namespace": obj.metadata.namespace,
                        "involved_object": obj.involved_object.name if obj.involved_object else "",
                        "involved_kind": obj.involved_object.kind if obj.involved_object else "",
                        "count": obj.count or 1,
                        "first_time": str(obj.first_timestamp) if obj.first_timestamp else "",
                        "last_time": str(obj.last_timestamp) if obj.last_timestamp else "",
                    }
                    await self._publish("events", ev_data)
            except ApiException as e:
                logger.warning(f"Event watch error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Event watch unexpected: {e}")
                await asyncio.sleep(10)

    async def _watch_nodes(self):
        v1 = get_core_v1()
        if not v1:
            return
        w = watch.Watch()
        while self._running:
            try:
                for event in w.stream(v1.list_node, timeout_seconds=60):
                    if not self._running:
                        break
                    obj = event["object"]
                    conditions = {c.type: c.status for c in (obj.status.conditions or [])}
                    capacity = obj.status.capacity or {}
                    allocatable = obj.status.allocatable or {}
                    node_data = {
                        "type": event["type"],
                        "node": obj.metadata.name,
                        "status": conditions.get("Ready", "Unknown"),
                        "capacity": {k: str(v) for k, v in capacity.items()},
                        "allocatable": {k: str(v) for k, v in allocatable.items()},
                        "labels": obj.metadata.labels or {},
                        "roles": [k.split("/")[-1] for k in (obj.metadata.labels or {}) if "node-role" in k],
                    }
                    await self._publish("nodes", node_data)
            except ApiException as e:
                logger.warning(f"Node watch error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Node watch unexpected: {e}")
                await asyncio.sleep(10)

    @staticmethod
    def _container_state(state) -> str:
        if not state:
            return "unknown"
        if state.running:
            return "running"
        if state.waiting:
            reason = state.waiting.reason or ""
            if "CrashLoop" in reason:
                return "crash_loop_backoff"
            if "ImagePull" in reason:
                return "image_pull_error"
            return f"waiting:{reason}"
        if state.terminated:
            reason = state.terminated.reason or ""
            if reason == "OOMKilled":
                return "oom_killed"
            if state.terminated.exit_code != 0:
                return f"error:{reason}"
            return "completed"
        return "unknown"


class RedisStreamConsumer:
    def __init__(self, redis_client, group="kubemind-consumers", consumer="backend-1"):
        self._redis = redis_client
        self._group = group
        self._consumer = consumer
        self._streams = ["kubemind:pods", "kubemind:events", "kubemind:nodes"]
        self._running = False

    async def start(self):
        self._running = True
        for stream in self._streams:
            try:
                await self._redis.xgroup_create(stream, self._group, id="0", mkstream=True)
            except Exception:
                pass
        logger.info(f"Redis consumer {self._consumer} started for group {self._group}")

    async def consume(self, callback):
        while self._running:
            try:
                results = await self._redis.xreadgroup(
                    group=self._group,
                    consumer=self._consumer,
                    streams={s: ">" for s in self._streams},
                    count=100,
                    block=2000,
                )
                if results:
                    for stream, messages in results:
                        for msg_id, msg_data in messages:
                            try:
                                raw = msg_data.get(b"data", msg_data.get("data", b"{}"))
                                if isinstance(raw, bytes):
                                    raw = raw.decode()
                                data = json.loads(raw) if isinstance(raw, str) else raw
                                await callback(stream.decode() if isinstance(stream, bytes) else stream, data)
                                await self._redis.xack(stream, self._group, msg_id)
                            except Exception as e:
                                logger.error(f"Consumer error: {e}")
            except Exception as e:
                logger.debug(f"Redis consume error: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self._running = False
