"""
KubeMind — Correlation Agent (Cross-Service Intelligence)
Detects cascading failures, root-cause chains, and cross-service influence.
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kubemind.agent.correlation")


class CorrelationAgent:
    def analyze(self, metrics: List[Dict], anomalies: List[Dict],
                topology: Optional[Dict] = None, ai_insights: List[Dict] = None) -> List[Dict]:
        insights = []
        if not anomalies:
            return insights

        anomaly_map = {a.get("service", ""): a for a in anomalies}
        metrics_map = {m["service"]: m for m in metrics}

        # Cascading failure detection
        ns_anomalies: Dict[str, List[str]] = defaultdict(list)
        for a in anomalies:
            ns_anomalies[a.get("namespace", "")].append(a.get("service", ""))

        for ns, svcs in ns_anomalies.items():
            if len(svcs) >= 3:
                scored = []
                for svc in svcs:
                    m = metrics_map.get(svc, {})
                    a = anomaly_map.get(svc, {})
                    score = ((10 if a.get("severity") == "critical" else 5)
                             + m.get("restart_count", 0) * 2
                             + (20 if m.get("crash_loop") else 0)
                             + (15 if m.get("oom_killed") else 0))
                    scored.append((svc, score))
                scored.sort(key=lambda x: x[1], reverse=True)
                root, victims = scored[0][0], [s[0] for s in scored[1:]]
                insights.append({
                    "agent": "correlation", "type": "cascade_failure", "severity": "critical",
                    "service": root, "namespace": ns,
                    "message": f"Cascading failure in {ns}: {root} is root cause, impacting {', '.join(victims[:4])}.",
                    "root_cause": root, "affected_services": victims,
                })

        # Node memory pressure
        high_mem = [m for m in metrics if m.get("memory_limit_mb", 0) > 0
                    and (m["memory_mb"] / m["memory_limit_mb"]) > 0.8]
        node_pressure: Dict[str, List[str]] = defaultdict(list)
        for m in high_mem:
            node_pressure[m.get("node_name", "unknown")].append(m["service"])
        for node, pods in node_pressure.items():
            if len(pods) >= 2:
                insights.append({
                    "agent": "correlation", "type": "node_memory_pressure", "severity": "warning",
                    "service": pods[0], "namespace": "",
                    "message": f"Node {node} memory pressure — {len(pods)} pods near limits: {', '.join(pods[:4])}.",
                })

        # Cross-domain synthesis
        if ai_insights:
            cpu_svcs = {i["service"] for i in ai_insights if i.get("agent") == "cpu" and i.get("severity") == "critical"}
            mem_svcs = {i["service"] for i in ai_insights if i.get("agent") == "memory" and i.get("severity") == "critical"}
            for svc in cpu_svcs & mem_svcs:
                m = metrics_map.get(svc, {})
                insights.append({
                    "agent": "correlation", "type": "resource_exhaustion", "severity": "critical",
                    "service": svc, "namespace": m.get("namespace", ""),
                    "message": f"{svc} CPU+memory exhaustion — immediate scaling required.",
                })

        return insights


correlation_agent = CorrelationAgent()
