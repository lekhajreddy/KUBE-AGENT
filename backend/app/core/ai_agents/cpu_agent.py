"""
KubeMind — CPU Intelligence Agent
Detects CPU spikes, throttling, noisy neighbors (pods on same node competing for CPU).
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger("kubemind.agent.cpu")


class CPUAgent:
    def __init__(self):
        self._history: Dict[str, List[float]] = {}

    def analyze(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        insights = []

        # Group pods by node for noisy neighbor detection
        node_pods: Dict[str, List[Dict]] = defaultdict(list)
        for m in metrics:
            node = m.get("node_name", "unknown")
            node_pods[node].append(m)
            # Track history
            svc = m["service"]
            self._history.setdefault(svc, []).append(m.get("cpu_percent", 0))
            if len(self._history[svc]) > 60:
                self._history[svc].pop(0)

        # ── CPU Spike Detection ───────────────────────────────────────────
        for m in metrics:
            cpu = m.get("cpu_percent", 0)
            svc = m["service"]
            ns = m.get("namespace", "")

            if cpu > 90:
                insights.append({
                    "agent": "cpu",
                    "type": "cpu_spike",
                    "severity": "critical",
                    "service": svc,
                    "namespace": ns,
                    "message": f"{svc} CPU at {cpu}% — critical spike detected. Consider HPA scale-out or resource limit increase.",
                    "value": cpu,
                    "threshold": 90,
                })
            elif cpu > 70:
                # Check if trending up
                hist = self._history.get(svc, [])
                if len(hist) >= 5 and all(hist[-i] > hist[-i-1] for i in range(1, min(4, len(hist)))):
                    insights.append({
                        "agent": "cpu",
                        "type": "cpu_trending_up",
                        "severity": "warning",
                        "service": svc,
                        "namespace": ns,
                        "message": f"{svc} CPU trending upward ({cpu}%) — approaching throttle threshold.",
                        "value": cpu,
                        "threshold": 70,
                    })

        # ── Noisy Neighbor Detection ──────────────────────────────────────
        for node, pods in node_pods.items():
            if len(pods) < 2:
                continue
            total_cpu = sum(p.get("cpu_percent", 0) for p in pods)
            if total_cpu > 150:  # Node under heavy load
                # Find the biggest consumer
                sorted_pods = sorted(pods, key=lambda p: p.get("cpu_percent", 0), reverse=True)
                hog = sorted_pods[0]
                victims = [p for p in sorted_pods[1:] if p.get("cpu_percent", 0) > 30]
                if victims:
                    victim_names = ", ".join(v["service"] for v in victims[:3])
                    insights.append({
                        "agent": "cpu",
                        "type": "noisy_neighbor",
                        "severity": "warning",
                        "service": hog["service"],
                        "namespace": hog.get("namespace", ""),
                        "message": f"{hog['service']} consuming {hog['cpu_percent']}% CPU on node {node} — "
                                   f"causing pressure on co-located pods: {victim_names}. "
                                   f"Consider pod anti-affinity rules.",
                        "node": node,
                        "affected_pods": [v["service"] for v in victims[:5]],
                    })

        # ── Throttling Detection ──────────────────────────────────────────
        for m in metrics:
            cpu = m.get("cpu_percent", 0)
            if cpu > 95 and m.get("latency_ms", 0) > 100:
                insights.append({
                    "agent": "cpu",
                    "type": "cpu_throttling",
                    "severity": "critical",
                    "service": m["service"],
                    "namespace": m.get("namespace", ""),
                    "message": f"{m['service']} likely CPU-throttled — {cpu}% usage with "
                               f"{m.get('latency_ms', 0)}ms latency. Increase CPU limits.",
                })

        return insights


cpu_agent = CPUAgent()
