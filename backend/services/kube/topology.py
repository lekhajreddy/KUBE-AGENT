"""
KubeMind — Topology Intelligence Engine
Builds and maintains a live dependency graph from K8s resources, network flows, and traces.
"""
import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set, Tuple

from backend.services.kube.discovery import resource_discovery

logger = logging.getLogger("kubemind.kube.topology")


class TopologyEdge:
    def __init__(self, source: str, target: str, edge_type: str,
                 namespace: str = "", latency_ms: float = 0.0,
                 error_rate: float = 0.0, traffic_rps: float = 0.0):
        self.source = source
        self.target = target
        self.type = edge_type
        self.namespace = namespace
        self.latency_ms = latency_ms
        self.error_rate = error_rate
        self.traffic_rps = traffic_rps

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "namespace": self.namespace,
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "traffic_rps": self.traffic_rps,
        }


class TopologyNode:
    def __init__(self, id: str, namespace: str, node_type: str,
                 status: str = "unknown", labels: dict = None):
        self.id = id
        self.namespace = namespace
        self.type = node_type
        self.status = status
        self.labels = labels or {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "type": self.type,
            "status": self.status,
            "labels": self.labels,
        }


class TopologyEngine:
    def __init__(self):
        self._nodes: Dict[str, TopologyNode] = {}
        self._edges: List[TopologyEdge] = []
        self._namespace_cache: Dict[str, List[str]] = defaultdict(list)

    async def build(self) -> Dict[str, Any]:
        self._nodes.clear()
        self._edges.clear()
        self._namespace_cache.clear()

        resources = resource_discovery.discover_all()

        # Add nodes from all resource types
        for pod in resources.get("pods", []):
            self._add_node(pod["name"], pod["namespace"], "pod", pod.get("status", "unknown"), pod.get("labels", {}))
            self._namespace_cache[pod["namespace"]].append(pod["name"])

        for svc in resources.get("services", []):
            self._add_node(svc["name"], svc["namespace"], "service", "active", svc.get("labels", {}))

        for dep in resources.get("deployments", []):
            self._add_node(dep["name"], dep["namespace"], "deployment", "active" if dep.get("ready_replicas", 0) > 0 else "inactive", dep.get("labels", {}))

        for pvc in resources.get("pvcs", []):
            self._add_node(pvc["name"], pvc["namespace"], "pvc", pvc.get("phase", "Pending"), pvc.get("labels", {}))

        for node in resources.get("nodes", []):
            self._add_node(node["name"], "cluster", "node", node.get("status", "Unknown"), node.get("labels", {}))

        for ns in resources.get("namespaces", []):
            self._add_node(ns["name"], "cluster", "namespace", ns.get("status", "Active"), ns.get("labels", {}))

        # Build edges from Service selectors to pods
        svc_map = {}
        for svc in resources.get("services", []):
            svc_map[svc["name"]] = svc

        for svc_name, svc in svc_map.items():
            selector = svc.get("selector", {})
            if not selector:
                continue
            for pod in resources.get("pods", []):
                if pod["namespace"] != svc["namespace"]:
                    continue
                pod_labels = pod.get("labels", {})
                if all(pod_labels.get(k) == v for k, v in selector.items()):
                    self._add_edge(svc_name, pod["name"], "selector", svc["namespace"])

        # Build edges from deployments to pods
        for dep in resources.get("deployments", []):
            dep_selector = dep.get("selector", {})
            if not dep_selector:
                continue
            for pod in resources.get("pods", []):
                if pod["namespace"] != dep["namespace"]:
                    continue
                pod_labels = pod.get("labels", {})
                if all(pod_labels.get(k) == v for k, v in dep_selector.items()):
                    self._add_edge(dep["name"], pod["name"], "owner", dep["namespace"])

        # Build edges from pods to PVCs
        for pvc in resources.get("pvcs", []):
            for pod in resources.get("pods", []):
                if pod["namespace"] != pvc["namespace"]:
                    continue
                for vol in (pod.get("volumes", [])):
                    pass  # Volume info not in discovery currently

        # Build cross-namespace edges from services to services (ingress routing)
        for ing in resources.get("ingresses", []):
            ing_ns = ing["namespace"]
            ing_name = ing["name"]
            self._add_node(f"ingress:{ing_name}", ing_ns, "ingress", "active")
            for rule in ing.get("rules", []):
                backend_svc = rule.get("service", "")
                if backend_svc:
                    self._add_edge(f"ingress:{ing_name}", backend_svc, "ingress_route", ing_ns)

        return self.snapshot()

    def _add_node(self, id: str, namespace: str, node_type: str,
                  status: str = "unknown", labels: dict = None):
        key = f"{namespace}/{id}" if namespace != "cluster" else id
        if key not in self._nodes:
            self._nodes[key] = TopologyNode(id, namespace, node_type, status, labels)
        else:
            existing = self._nodes[key]
            if status != "unknown":
                existing.status = status
            if labels:
                existing.labels.update(labels)

    def _add_edge(self, source: str, target: str, edge_type: str, namespace: str = ""):
        for edge in self._edges:
            if edge.source == source and edge.target == target and edge.type == edge_type:
                return
        self._edges.append(TopologyEdge(source, target, edge_type, namespace))

    def update_edge_telemetry(self, source: str, target: str,
                               latency_ms: float = 0.0, error_rate: float = 0.0,
                               traffic_rps: float = 0.0):
        for edge in self._edges:
            if edge.source == source and edge.target == target:
                edge.latency_ms = latency_ms
                edge.error_rate = error_rate
                edge.traffic_rps = traffic_rps
                break

    def get_critical_paths(self, anomaly_services: Set[str]) -> List[Dict]:
        paths = []
        for anomaly in anomaly_services:
            chain = [anomaly]
            visited = {anomaly}
            # Walk upstream
            current = anomaly
            for _ in range(5):
                found = False
                for edge in self._edges:
                    if edge.target == current and edge.source not in visited:
                        chain.insert(0, edge.source)
                        visited.add(edge.source)
                        current = edge.source
                        found = True
                        break
                if not found:
                    break
            # Walk downstream
            current = anomaly
            for _ in range(5):
                found = False
                for edge in self._edges:
                    if edge.source == current and edge.target not in visited:
                        chain.append(edge.target)
                        visited.add(edge.target)
                        current = edge.target
                        found = True
                        break
                if not found:
                    break
            if len(chain) > 1:
                paths.append({"root": anomaly, "chain": chain})
        return paths

    def snapshot(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges],
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
        }


topology_engine = TopologyEngine()
