"""
KubeMind Agent — Runs inside customer Kubernetes clusters
Collects metrics, discovers topology, and pushes telemetry to KubeMind backend via WebSocket.
"""
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("kubemind-agent")

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_URL = os.environ.get("KUBEMIND_BACKEND_URL", "ws://localhost:8000/ws/agent")
API_KEY = os.environ.get("KUBEMIND_API_KEY", "")
CLUSTER_ID = os.environ.get("KUBEMIND_CLUSTER_ID", "")
COLLECTION_INTERVAL = int(os.environ.get("KUBEMIND_INTERVAL", "5"))
AGENT_VERSION = "1.0.0"

# ── K8s client init ───────────────────────────────────────────────────────────
_core_v1 = None
_apps_v1 = None
_custom = None

def _init_k8s():
    global _core_v1, _apps_v1, _custom
    from kubernetes import client, config as k8s_config
    try:
        k8s_config.load_incluster_config()
        logger.info("K8s: loaded in-cluster config")
    except Exception:
        k8s_config.load_kube_config()
        logger.info("K8s: loaded local kubeconfig")
    _core_v1 = client.CoreV1Api()
    _apps_v1 = client.AppsV1Api()
    _custom = client.CustomObjectsApi()


def _collect_pods() -> List[Dict]:
    if not _core_v1:
        return []
    pods = []
    try:
        for pod in _core_v1.list_pod_for_all_namespaces(watch=False).items:
            meta, spec, status = pod.metadata, pod.spec, pod.status
            restart_count, oom, crash = 0, False, False
            for cs in (status.container_statuses or []):
                restart_count += cs.restart_count or 0
                if cs.last_state and cs.last_state.terminated and cs.last_state.terminated.reason == "OOMKilled":
                    oom = True
                if cs.state and cs.state.waiting and "CrashLoopBackOff" in (cs.state.waiting.reason or ""):
                    crash = True
            phase = status.phase or "Unknown"
            pod_status = "CrashLoopBackOff" if crash else "OOMKilled" if oom else phase if phase in ("Failed","Unknown","Pending") else "Running"
            pods.append({
                "name": meta.name, "namespace": meta.namespace, "node_name": spec.node_name or "unscheduled",
                "status": pod_status, "phase": phase, "restart_count": restart_count,
                "oom_killed": oom, "crash_loop": crash, "labels": meta.labels or {},
                "ready": sum(1 for cs in (status.container_statuses or []) if cs.ready),
                "total_containers": len(spec.containers) if spec.containers else 1,
            })
    except Exception as e:
        logger.error(f"Pod collection error: {e}")
    return pods


def _collect_metrics_api() -> Dict[str, Dict]:
    if not _custom:
        return {}
    result = {}
    try:
        res = _custom.list_cluster_custom_object(group="metrics.k8s.io", version="v1beta1", plural="pods")
        for item in res.get("items", []):
            name = item["metadata"]["name"]
            ns = item["metadata"]["namespace"]
            cpu_sum, mem_sum = 0, 0
            for c in item.get("containers", []):
                usage = c.get("usage", {})
                cpu_str = usage.get("cpu", "0n")
                mem_str = usage.get("memory", "0Ki")
                if cpu_str.endswith("n"): cpu_sum += int(cpu_str[:-1])
                elif cpu_str.endswith("m"): cpu_sum += int(float(cpu_str[:-1]) * 1_000_000)
                if mem_str.endswith("Ki"): mem_sum += int(mem_str[:-2]) * 1024
                elif mem_str.endswith("Mi"): mem_sum += int(mem_str[:-2]) * 1048576
            result[f"{ns}/{name}"] = {"cpu_nano": cpu_sum, "mem_bytes": mem_sum}
    except Exception as e:
        logger.warning(f"Metrics API: {e}")
    return result


def _collect_deployments() -> List[Dict]:
    if not _apps_v1:
        return []
    deps = []
    try:
        for dep in _apps_v1.list_deployment_for_all_namespaces(watch=False).items:
            deps.append({
                "name": dep.metadata.name, "namespace": dep.metadata.namespace,
                "replicas": dep.spec.replicas or 1, "ready_replicas": dep.status.ready_replicas or 0,
                "selector": dep.spec.selector.match_labels if dep.spec.selector else {},
            })
    except Exception as e:
        logger.warning(f"Deployment collection: {e}")
    return deps


def _collect_services() -> List[Dict]:
    if not _core_v1:
        return []
    svcs = []
    try:
        for svc in _core_v1.list_service_for_all_namespaces(watch=False).items:
            svcs.append({
                "name": svc.metadata.name, "namespace": svc.metadata.namespace,
                "selector": svc.spec.selector or {}, "type": svc.spec.type or "ClusterIP",
            })
    except Exception as e:
        logger.warning(f"Service collection: {e}")
    return svcs


def _build_metrics(pods, metrics_api, deployments) -> List[Dict]:
    ts = datetime.now(timezone.utc).isoformat()
    DEFAULT_CPU_CAP = 2_000_000_000
    result = []
    for pod in pods:
        key = f"{pod['namespace']}/{pod['name']}"
        raw = metrics_api.get(key, {})
        cpu_pct = round((raw.get("cpu_nano", 0) / DEFAULT_CPU_CAP) * 100, 2)
        mem_mb = round(raw.get("mem_bytes", 0) / 1048576, 1)
        dep_info = None
        for dep in deployments:
            if dep["namespace"] == pod["namespace"]:
                dep_sel = dep.get("selector", {})
                if dep_sel and all(pod["labels"].get(k) == v for k, v in dep_sel.items()):
                    dep_info = dep
                    break
        result.append({
            "service": pod["name"], "namespace": pod["namespace"], "node_name": pod["node_name"],
            "domain": pod["namespace"], "timestamp": ts, "status": pod["status"], "phase": pod["phase"],
            "replicas": dep_info["replicas"] if dep_info else 1,
            "ready_replicas": dep_info["ready_replicas"] if dep_info else (1 if pod["status"] == "Running" else 0),
            "cpu_percent": cpu_pct, "memory_mb": mem_mb, "memory_limit_mb": max(mem_mb * 2, 256),
            "network_in_kbps": 0, "network_out_kbps": 0, "pvc_usage_percent": 0, "disk_usage_percent": 0,
            "restart_count": pod["restart_count"], "oom_killed": pod["oom_killed"],
            "crash_loop": pod["crash_loop"], "latency_ms": 0, "error_rate_percent": 0,
        })
    return result


def _build_topology(deployments, services):
    nodes, links = [], []
    ns_deps = {}
    for dep in deployments:
        ns_deps.setdefault(dep["namespace"], []).append(dep["name"])
        nodes.append({"id": dep["name"], "namespace": dep["namespace"], "domain": dep["namespace"],
                       "replicas": dep["replicas"], "ready_replicas": dep["ready_replicas"], "type": "deployment"})
    for ns, dep_names in ns_deps.items():
        for i in range(1, len(dep_names)):
            links.append({"source": dep_names[0], "target": dep_names[i]})
    return {"nodes": nodes, "links": links}


# ── WebSocket client ──────────────────────────────────────────────────────────
async def _agent_loop():
    import websockets
    ws_url = f"{BACKEND_URL}?api_key={API_KEY}&cluster_id={CLUSTER_ID}"
    
    while True:
        try:
            logger.info(f"Connecting to {BACKEND_URL}...")
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=30) as ws:
                logger.info("✅ Connected to KubeMind backend")

                while True:
                    # Collect
                    pods = _collect_pods()
                    metrics_api = _collect_metrics_api()
                    deployments = _collect_deployments()
                    services = _collect_services()

                    metrics = _build_metrics(pods, metrics_api, deployments)
                    topology = _build_topology(deployments, services)

                    # Push metrics
                    await ws.send(json.dumps({"type": "metrics", "data": {
                        "metrics": metrics, "cluster_id": CLUSTER_ID,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }}, default=str))

                    # Push topology
                    await ws.send(json.dumps({"type": "topology", "data": topology}, default=str))

                    # Heartbeat
                    await ws.send(json.dumps({"type": "heartbeat", "agent_info": {
                        "version": AGENT_VERSION, "cluster_id": CLUSTER_ID,
                        "pod_count": len(pods), "provider": "in-cluster",
                    }}))

                    # Wait for ack
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=2)
                    except asyncio.TimeoutError:
                        pass

                    await asyncio.sleep(COLLECTION_INTERVAL)

        except Exception as e:
            logger.error(f"Connection error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)


def main():
    if not API_KEY:
        logger.error("KUBEMIND_API_KEY not set!")
        sys.exit(1)
    if not CLUSTER_ID:
        logger.error("KUBEMIND_CLUSTER_ID not set!")
        sys.exit(1)

    logger.info(f"KubeMind Agent v{AGENT_VERSION} starting | cluster={CLUSTER_ID}")
    _init_k8s()
    asyncio.run(_agent_loop())


if __name__ == "__main__":
    main()
