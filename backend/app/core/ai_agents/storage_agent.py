"""
KubeMind — Storage Intelligence Agent
Detects PVC saturation, IO bottlenecks, and storage-related pod failures.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger("kubemind.agent.storage")


class StorageAgent:
    def __init__(self):
        self._history: Dict[str, List[float]] = {}

    def analyze(self, metrics: List[Dict[str, Any]], pvcs: List[Dict] = None) -> List[Dict[str, Any]]:
        insights = []

        for m in metrics:
            svc = m["service"]
            ns = m.get("namespace", "")
            pvc_pct = m.get("pvc_usage_percent", 0)
            disk_pct = m.get("disk_usage_percent", 0)
            usage = max(pvc_pct, disk_pct)

            # Track history
            self._history.setdefault(svc, []).append(usage)
            if len(self._history[svc]) > 60:
                self._history[svc].pop(0)

            # ── PVC Saturation ────────────────────────────────────────────
            if usage > 95:
                insights.append({
                    "agent": "storage",
                    "type": "pvc_saturation",
                    "severity": "critical",
                    "service": svc,
                    "namespace": ns,
                    "message": f"{svc} PVC at {usage:.1f}% — storage nearly full. "
                               f"Immediate expansion required or data cleanup needed. "
                               f"Risk of pod eviction and data loss.",
                    "value": usage,
                    "threshold": 95,
                })
            elif usage > 80:
                # Check growth trend
                hist = self._history.get(svc, [])
                if len(hist) >= 10:
                    growth = hist[-1] - hist[-10]
                    if growth > 5:  # 5% growth in last 10 samples
                        time_to_full = (100 - usage) / (growth / 10) if growth > 0 else float("inf")
                        insights.append({
                            "agent": "storage",
                            "type": "pvc_filling",
                            "severity": "warning",
                            "service": svc,
                            "namespace": ns,
                            "message": f"{svc} PVC at {usage:.1f}% and growing — estimated full in "
                                       f"~{time_to_full:.0f} collection intervals. Plan capacity expansion.",
                            "value": usage,
                        })

            # ── IO Bottleneck inference ───────────────────────────────────
            # High disk usage + high latency → possible IO bottleneck
            latency = m.get("latency_ms", 0)
            if usage > 70 and latency > 200:
                insights.append({
                    "agent": "storage",
                    "type": "io_bottleneck",
                    "severity": "warning",
                    "service": svc,
                    "namespace": ns,
                    "message": f"{svc} showing IO bottleneck — disk at {usage:.1f}% with "
                               f"{latency}ms latency. Consider migrating to SSD-backed StorageClass "
                               f"or reducing write-heavy operations.",
                    "value": usage,
                    "latency_ms": latency,
                })

        # ── PVC-related pod restart correlation ───────────────────────────
        restarting_with_storage = [
            m for m in metrics
            if m.get("restart_count", 0) >= 3 and m.get("pvc_usage_percent", 0) > 85
        ]
        if restarting_with_storage:
            for m in restarting_with_storage:
                insights.append({
                    "agent": "storage",
                    "type": "storage_restart_correlation",
                    "severity": "critical",
                    "service": m["service"],
                    "namespace": m.get("namespace", ""),
                    "message": f"{m['service']} restarting ({m['restart_count']}x) with PVC at "
                               f"{m['pvc_usage_percent']:.1f}% — storage pressure likely causing restarts. "
                               f"PVC saturation causing pod restart cascade.",
                })

        return insights


storage_agent = StorageAgent()
