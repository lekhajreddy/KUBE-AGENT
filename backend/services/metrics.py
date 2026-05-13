"""
KubeMind — Prometheus Metrics Collector Service
Real-time PromQL queries with aggregation, caching, and streaming.
"""
import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable

import aiohttp

logger = logging.getLogger("kubemind.metrics")


class PrometheusCollector:
    CPU_QUERY = 'sum(rate(container_cpu_usage_seconds_total[1m])) by (pod, namespace)'
    MEMORY_QUERY = 'sum(container_memory_working_set_bytes) by (pod, namespace)'
    RESTARTS_QUERY = 'sum(kube_pod_container_status_restarts_total) by (pod, namespace)'
    NETWORK_RX_QUERY = 'sum(rate(container_network_receive_bytes_total[1m])) by (pod, namespace)'
    NETWORK_TX_QUERY = 'sum(rate(container_network_transmit_bytes_total[1m])) by (pod, namespace)'
    PVC_USAGE_QUERY = 'sum(kubelet_volume_stats_used_bytes) by (namespace, persistentvolumeclaim)'
    PVC_CAPACITY_QUERY = 'sum(kubelet_volume_stats_capacity_bytes) by (namespace, persistentvolumeclaim)'
    CPU_CAPACITY_QUERY = 'sum(kube_node_status_capacity{resource="cpu"}) by (node)'

    def __init__(self, prometheus_url: str = "http://prometheus:9090"):
        self._prometheus_url = prometheus_url.rstrip("/")
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: float = 5.0
        self._last_fetch: float = 0.0
        self._listeners: List[Callable] = []
        self._running = False

    def register_listener(self, callback: Callable):
        self._listeners.append(callback)

    async def query(self, query: str, timeout: float = 10.0) -> List[dict]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                url = f"{self._prometheus_url}/api/v1/query"
                async with session.get(url, params={"query": query}) as resp:
                    if resp.status != 200:
                        logger.warning(f"Prometheus query failed: {resp.status}")
                        return []
                    data = await resp.json()
                    return data.get("data", {}).get("result", [])
        except Exception as e:
            logger.debug(f"Prometheus query error [{query[:50]}]: {e}")
            return []

    async def collect_all(self) -> List[Dict[str, Any]]:
        now = time.time()
        if now - self._last_fetch < self._cache_ttl and self._cache:
            return self._cache.get("metrics", [])

        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                self._query(self.CPU_QUERY, session),
                self._query(self.MEMORY_QUERY, session),
                self._query(self.RESTARTS_QUERY, session),
                self._query(self.NETWORK_RX_QUERY, session),
                self._query(self.NETWORK_TX_QUERY, session),
                self._query(self.PVC_USAGE_QUERY, session),
                self._query(self.PVC_CAPACITY_QUERY, session),
                return_exceptions=True,
            )

        cpu_data, mem_data, restarts_data = results[0], results[1], results[2]
        net_rx, net_tx, pvc_usage, pvc_cap = results[3], results[4], results[5], results[6]

        if isinstance(cpu_data, Exception):
            cpu_data = []
        if isinstance(mem_data, Exception):
            mem_data = []

        cpu_map = self._to_map(cpu_data, "pod", "namespace")
        mem_map = self._to_map(mem_data, "pod", "namespace")
        restart_map = self._to_map(results[2] if not isinstance(results[2], Exception) else [], "pod", "namespace")
        net_rx_map = self._to_map(results[3] if not isinstance(results[3], Exception) else [], "pod", "namespace")
        net_tx_map = self._to_map(results[4] if not isinstance(results[4], Exception) else [], "pod", "namespace")
        pvc_usage_map = self._to_map(results[5] if not isinstance(results[5], Exception) else [], "persistentvolumeclaim", "namespace")
        pvc_cap_map = self._to_map(results[6] if not isinstance(results[6], Exception) else [], "persistentvolumeclaim", "namespace")

        all_keys = set()
        all_keys.update(cpu_map.keys())
        all_keys.update(mem_map.keys())

        ts = datetime.now(timezone.utc).isoformat()
        DEFAULT_CPU_CAPACITY = 2.0

        metrics = []
        for key in all_keys:
            parts = key.split("/", 1)
            if len(parts) != 2:
                continue
            ns, pod = parts[0], parts[1]

            cpu_val = self._float_value(cpu_map.get(key, {}).get("value", 0))
            cpu_cores = cpu_val  # Already in cores/sec
            cpu_percent = min(round((cpu_cores / DEFAULT_CPU_CAPACITY) * 100, 2), 100)

            mem_bytes = self._float_value(mem_map.get(key, {}).get("value", 0))
            memory_mb = round(mem_bytes / (1024 * 1024), 1)

            restart_count = int(self._float_value(restart_map.get(key, {}).get("value", 0)))

            net_rx_val = self._float_value(net_rx_map.get(key, {}).get("value", 0))
            net_tx_val = self._float_value(net_tx_map.get(key, {}).get("value", 0))
            net_in_kbps = round(net_rx_val / 1024, 1)
            net_out_kbps = round(net_tx_val / 1024, 1)

            metrics.append({
                "service": pod,
                "pod_name": pod,
                "namespace": ns,
                "timestamp": ts,
                "cpu_percent": cpu_percent,
                "cpu_cores": round(cpu_cores, 3),
                "memory_mb": memory_mb,
                "memory_bytes": int(mem_bytes),
                "restart_count": restart_count,
                "network_in_kbps": net_in_kbps,
                "network_out_kbps": net_out_kbps,
                "status": "Running",
            })

        self._cache["metrics"] = metrics
        self._last_fetch = now

        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(metrics)
                else:
                    listener(metrics)
            except Exception as e:
                logger.error(f"Metrics listener error: {e}")

        return metrics

    async def _query(self, query: str, session: aiohttp.ClientSession) -> List[dict]:
        try:
            url = f"{self._prometheus_url}/api/v1/query"
            async with session.get(url, params={"query": query}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("data", {}).get("result", [])
        except Exception as e:
            logger.debug(f"PromQL error: {e}")
            return []

    def _to_map(self, results: List[dict], *label_keys: str) -> Dict[str, dict]:
        mapping = {}
        for r in results:
            metric = r.get("metric", {})
            key_parts = []
            for k in label_keys:
                val = metric.get(k, "")
                if val:
                    key_parts.append(val)
            if not key_parts:
                continue
            key = "/".join(key_parts)
            try:
                value = float(r["value"][1])
            except (IndexError, ValueError, TypeError):
                value = 0.0
            mapping[key] = {"value": value, "labels": metric}
        return mapping

    @staticmethod
    def _float_value(val) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0


class MetricsAggregator:
    def __init__(self, window_size: int = 10):
        self._window: Dict[str, List[dict]] = defaultdict(list)
        self.window_size = window_size

    def ingest(self, metrics: List[dict]):
        for m in metrics:
            key = f"{m.get('namespace', '')}/{m.get('service', '')}"
            self._window[key].append(m)
            if len(self._window[key]) > self.window_size:
                self._window[key].pop(0)

    def get_aggregated(self, metric: str = "cpu_percent") -> Dict[str, float]:
        result = {}
        for key, vals in self._window.items():
            values = [v.get(metric, 0) for v in vals if v.get(metric) is not None]
            if values:
                result[key] = round(sum(values) / len(values), 2)
        return result

    def get_trend(self, key: str, metric: str = "cpu_percent") -> str:
        vals = [v.get(metric, 0) for v in self._window.get(key, []) if v.get(metric) is not None]
        if len(vals) < 3:
            return "stable"
        recent = sum(vals[-3:]) / 3
        earlier = sum(vals[:3]) / 3
        diff = recent - earlier
        if diff > 5:
            return "rising"
        if diff < -5:
            return "falling"
        return "stable"


prometheus_collector = PrometheusCollector()
metrics_aggregator = MetricsAggregator()
