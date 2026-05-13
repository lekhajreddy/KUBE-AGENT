"""
KubeMind — Root Cause Analysis Engine (Real Kubernetes Edition)
Dynamic dependency graph built from live K8s topology.
Uses NetworkX for graph traversal and cascade failure detection.
"""
from typing import Any, Dict, List, Optional
import logging

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

logger = logging.getLogger("kubemind.rca")


class RCAEngine:
    """
    Analyzes anomalies across live Kubernetes pods/deployments.
    Dependency graph is passed in dynamically from k8s_collector topology,
    NOT hardcoded as it was in the simulated version.
    """

    def _build_graph(self, topology: Optional[Dict]) -> "nx.DiGraph | None":
        if not _NX_AVAILABLE or not topology:
            return None
        G = nx.DiGraph()
        for node in topology.get("nodes", []):
            G.add_node(node["id"], namespace=node.get("namespace", ""), domain=node.get("domain", ""))
        for link in topology.get("links", []):
            G.add_edge(link["source"], link["target"])
        return G

    def _infer_deps_from_namespace(self, anomalies: List[Dict]) -> Dict[str, List[str]]:
        """
        Fallback: group by namespace. Services in same namespace
        can potentially be upstream/downstream of each other.
        """
        ns_map: Dict[str, List[str]] = {}
        for a in anomalies:
            ns = a.get("namespace", "default")
            ns_map.setdefault(ns, []).append(a["service"])
        # Build simple chain within each namespace
        dep_map: Dict[str, List[str]] = {}
        for ns, svcs in ns_map.items():
            for i, svc in enumerate(svcs):
                dep_map[svc] = svcs[:i]  # depends on all earlier in same ns
        return dep_map

    def analyze(
        self,
        anomalies: List[Dict[str, Any]],
        metrics: List[Dict[str, Any]],
        topology: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        For each anomalous pod, determine root cause vs. downstream victim.
        Uses live K8s topology when available, falls back to namespace grouping.
        """
        if not anomalies:
            return []

        # Build dependency map from live topology
        dep_map: Dict[str, List[str]] = {}
        graph = self._build_graph(topology)

        if graph and _NX_AVAILABLE:
            for node in graph.nodes():
                # predecessors = what this node depends on
                dep_map[node] = list(graph.predecessors(node))
        else:
            dep_map = self._infer_deps_from_namespace(anomalies)

        anomaly_set = {a["service"] for a in anomalies}

        # Build metrics lookup
        metrics_map = {m["service"]: m for m in metrics}

        results = []
        for anomaly in anomalies:
            svc = anomaly["service"]
            upstream_faulty = [u for u in dep_map.get(svc, []) if u in anomaly_set]

            # Find downstream pods at risk (in same namespace, not yet anomalous)
            if graph and _NX_AVAILABLE and svc in graph:
                downstream = [
                    s for s in graph.successors(svc)
                    if s not in anomaly_set
                ]
            else:
                svc_ns = anomaly.get("namespace", "")
                downstream = [
                    m["service"] for m in metrics
                    if m["namespace"] == svc_ns
                    and m["service"] not in anomaly_set
                    and m["service"] != svc
                ]

            is_root = len(upstream_faulty) == 0
            m_data  = metrics_map.get(svc, {})
            ns      = anomaly.get("namespace", m_data.get("namespace", ""))

            # Build detailed reasoning
            atypes = anomaly.get("anomaly_types", [])
            if is_root:
                reasoning = (
                    f"{svc} ({ns}) is the originating failure point — "
                    f"no upstream dependencies are anomalous. "
                    f"Detected: {', '.join(atypes) or 'multiple signals'}."
                )
                if m_data.get("crash_loop"):
                    reasoning += " Pod is in CrashLoopBackOff."
                if m_data.get("oom_killed"):
                    reasoning += " Pod was OOMKilled — memory limit too low."
            else:
                reasoning = (
                    f"{svc} ({ns}) is likely impacted by upstream failures in: "
                    f"{', '.join(upstream_faulty)}. "
                    f"Consider fixing root causes before restarting this pod."
                )

            # Cascade chain via NetworkX if available
            cascade_chain: List[str] = []
            if graph and _NX_AVAILABLE and is_root:
                try:
                    for target in downstream:
                        if nx.has_path(graph, svc, target):
                            cascade_chain.append(target)
                except Exception:
                    pass

            results.append({
                "service":           svc,
                "namespace":         ns,
                "is_root_cause":     is_root,
                "reasoning":         reasoning,
                "severity":          anomaly.get("severity", "warning"),
                "upstream_faulty":   upstream_faulty,
                "at_risk_downstream": downstream[:5],
                "cascade_chain":     cascade_chain[:5],
                "anomaly_types":     atypes,
                "crash_loop":        m_data.get("crash_loop", False),
                "oom_killed":        m_data.get("oom_killed", False),
                "restart_count":     m_data.get("restart_count", 0),
            })

        # Sort: root causes first, then severity
        severity_order = {"critical": 0, "warning": 1, "normal": 2}
        results.sort(key=lambda r: (
            not r["is_root_cause"],
            severity_order.get(r["severity"], 9)
        ))
        return results


rca_engine = RCAEngine()
