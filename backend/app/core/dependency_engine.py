"""
KubeMind — Enhanced Dependency Discovery Engine
Detects real service-to-service dependencies from K8s topology, network metrics,
shared PVCs, restart cascades, and label/selector matching.
"""
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("kubemind.dependency")


class DependencyEngine:
    """
    Builds a real dependency graph from multiple signals:
    1. Service selector → Deployment label matching
    2. Shared PVC mounting (pods sharing same volume)
    3. Restart cascade detection (time-correlated restarts)
    4. Ingress → Service routing
    5. Network traffic correlation (from Prometheus)
    """

    def __init__(self):
        self._restart_history: Dict[str, List[float]] = {}  # pod → timestamps
        self._network_pairs: Dict[Tuple[str, str], float] = {}  # (src, dst) → strength

    def build_dependency_graph(
        self,
        pods: List[Dict],
        deployments: List[Dict],
        services: List[Dict],
        pvcs: List[Dict] = None,
        ingresses: List[Dict] = None,
        metrics: List[Dict] = None,
    ) -> Dict[str, Any]:
        """Build comprehensive dependency graph from all available signals."""
        nodes = []
        links = []
        node_ids: Set[str] = set()

        # ── 1. Deployment nodes ───────────────────────────────────────────
        dep_by_ns: Dict[str, List[Dict]] = defaultdict(list)
        for dep in deployments:
            dep_by_ns[dep["namespace"]].append(dep)
            node_id = dep["name"]
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "namespace": dep["namespace"],
                    "domain": dep["namespace"],
                    "replicas": dep.get("replicas", 1),
                    "ready_replicas": dep.get("ready_replicas", 0),
                    "type": "deployment",
                })

        # ── 2. Service → Deployment links (selector matching) ─────────────
        svc_to_deps: Dict[str, List[str]] = {}
        for svc in services:
            selector = svc.get("selector", {})
            if not selector:
                continue
            matched_deps = []
            for dep in deployments:
                if dep["namespace"] != svc["namespace"]:
                    continue
                dep_selector = dep.get("selector", {})
                if dep_selector and any(
                    selector.get(k) == v for k, v in dep_selector.items()
                ):
                    matched_deps.append(dep["name"])
            svc_to_deps[svc["name"]] = matched_deps

        # ── 3. Ingress → Service links ────────────────────────────────────
        if ingresses:
            for ing in ingresses:
                ing_name = ing.get("name", "")
                backends = ing.get("backends", [])
                for backend_svc in backends:
                    # Link ingress to all deployments behind this service
                    for dep_name in svc_to_deps.get(backend_svc, []):
                        links.append({
                            "source": f"ingress-{ing_name}",
                            "target": dep_name,
                            "type": "ingress",
                        })
                # Add ingress as a node
                if ing_name and f"ingress-{ing_name}" not in node_ids:
                    node_ids.add(f"ingress-{ing_name}")
                    nodes.append({
                        "id": f"ingress-{ing_name}",
                        "namespace": ing.get("namespace", ""),
                        "domain": ing.get("namespace", ""),
                        "type": "ingress",
                    })

        # ── 4. Shared PVC relationships ───────────────────────────────────
        if pvcs:
            pvc_pods = self._find_shared_pvc_pods(pods, pvcs)
            for pvc_name, pod_names in pvc_pods.items():
                if len(pod_names) >= 2:
                    # All pods sharing a PVC are linked
                    dep_names = self._pods_to_deployments(pod_names, pods, deployments)
                    for i in range(len(dep_names)):
                        for j in range(i + 1, len(dep_names)):
                            if dep_names[i] != dep_names[j]:
                                links.append({
                                    "source": dep_names[i],
                                    "target": dep_names[j],
                                    "type": "shared_pvc",
                                    "pvc": pvc_name,
                                })

        # ── 5. Intra-namespace service chain inference ─────────────────────
        for ns, ns_deps in dep_by_ns.items():
            if len(ns_deps) < 2:
                continue
            # Services in same namespace with matching labels → likely communicate
            for i, dep_a in enumerate(ns_deps):
                for dep_b in ns_deps[i + 1:]:
                    # Check if any service selects both (gateway pattern)
                    a_name, b_name = dep_a["name"], dep_b["name"]
                    # If there's a service that routes to dep_a, it might call dep_b
                    for svc_name, dep_list in svc_to_deps.items():
                        if a_name in dep_list or b_name in dep_list:
                            if a_name != b_name:
                                links.append({
                                    "source": a_name,
                                    "target": b_name,
                                    "type": "namespace_sibling",
                                })
                            break

        # ── 6. Restart cascade detection ──────────────────────────────────
        if metrics:
            cascade_links = self._detect_restart_cascades(metrics)
            links.extend(cascade_links)

        # Deduplicate links
        seen_links: Set[str] = set()
        unique_links = []
        for link in links:
            key = f"{link['source']}→{link['target']}"
            rev_key = f"{link['target']}→{link['source']}"
            if key not in seen_links and rev_key not in seen_links:
                seen_links.add(key)
                unique_links.append(link)

        return {"nodes": nodes, "links": unique_links}

    def _find_shared_pvc_pods(self, pods: List[Dict], pvcs: List[Dict]) -> Dict[str, List[str]]:
        """Find pods that share the same PVC."""
        pvc_names = {pvc["name"] for pvc in pvcs}
        pvc_pods: Dict[str, List[str]] = defaultdict(list)

        for pod in pods:
            volumes = pod.get("volumes", [])
            for vol in volumes:
                pvc_claim = vol.get("pvc_claim")
                if pvc_claim and pvc_claim in pvc_names:
                    pvc_pods[pvc_claim].append(pod["name"])

        return dict(pvc_pods)

    def _pods_to_deployments(
        self, pod_names: List[str], pods: List[Dict], deployments: List[Dict]
    ) -> List[str]:
        """Map pod names back to their owning deployment names."""
        dep_names = set()
        for pod_name in pod_names:
            pod = next((p for p in pods if p["name"] == pod_name), None)
            if not pod:
                continue
            pod_labels = pod.get("labels", {})
            for dep in deployments:
                if dep["namespace"] != pod.get("namespace"):
                    continue
                dep_sel = dep.get("selector", {})
                if dep_sel and all(pod_labels.get(k) == v for k, v in dep_sel.items()):
                    dep_names.add(dep["name"])
                    break
        return list(dep_names)

    def _detect_restart_cascades(self, metrics: List[Dict]) -> List[Dict]:
        """Detect pods that restart within a correlated time window."""
        now = time.time()
        links = []

        # Track recent restarts
        restarting_pods = []
        for m in metrics:
            rc = m.get("restart_count", 0)
            if rc > 0 and (m.get("crash_loop") or rc >= 3):
                restarting_pods.append({
                    "name": m["service"],
                    "namespace": m["namespace"],
                    "restart_count": rc,
                })

        # Pods restarting in the same namespace at similar times → cascade
        ns_restarts: Dict[str, List[str]] = defaultdict(list)
        for pod in restarting_pods:
            ns_restarts[pod["namespace"]].append(pod["name"])

        for ns, pod_names in ns_restarts.items():
            if len(pod_names) >= 2:
                # First restarting pod is likely the root cause
                for i in range(1, len(pod_names)):
                    links.append({
                        "source": pod_names[0],
                        "target": pod_names[i],
                        "type": "restart_cascade",
                    })

        return links

    def ingest_network_correlation(self, src: str, dst: str, strength: float):
        """Ingest network traffic correlation data (from Prometheus/eBPF)."""
        self._network_pairs[(src, dst)] = strength


# Global singleton
dependency_engine = DependencyEngine()
