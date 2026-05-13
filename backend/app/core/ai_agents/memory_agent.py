"""
KubeMind — Memory Intelligence Agent
Detects memory leaks (monotonic growth), abnormal growth patterns, and OOM prediction.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger("kubemind.agent.memory")


class MemoryAgent:
    def __init__(self):
        self._history: Dict[str, List[float]] = {}

    def analyze(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        insights = []

        for m in metrics:
            svc = m["service"]
            ns = m.get("namespace", "")
            mem_mb = m.get("memory_mb", 0)
            mem_limit = m.get("memory_limit_mb", 512)

            # Track history
            self._history.setdefault(svc, []).append(mem_mb)
            if len(self._history[svc]) > 120:
                self._history[svc].pop(0)

            usage_pct = (mem_mb / mem_limit * 100) if mem_limit > 0 else 0

            # ── OOM Prediction ────────────────────────────────────────────
            if m.get("oom_killed"):
                insights.append({
                    "agent": "memory",
                    "type": "oom_killed",
                    "severity": "critical",
                    "service": svc,
                    "namespace": ns,
                    "message": f"{svc} was OOMKilled — memory limit ({mem_limit}MB) exceeded. "
                               f"Increase limits: kubectl set resources deployment/{svc} -n {ns} --limits=memory={int(mem_limit * 1.5)}Mi",
                    "value": mem_mb,
                    "limit": mem_limit,
                })
                continue

            # ── Near-OOM Warning ──────────────────────────────────────────
            if usage_pct > 85:
                insights.append({
                    "agent": "memory",
                    "type": "near_oom",
                    "severity": "critical" if usage_pct > 95 else "warning",
                    "service": svc,
                    "namespace": ns,
                    "message": f"{svc} memory at {usage_pct:.0f}% of limit ({mem_mb:.0f}/{mem_limit:.0f}MB) — "
                               f"OOM risk imminent. Increase memory limit or fix leak.",
                    "value": mem_mb,
                    "limit": mem_limit,
                    "usage_pct": round(usage_pct, 1),
                })

            # ── Memory Leak Detection (monotonic increase) ────────────────
            hist = self._history.get(svc, [])
            if len(hist) >= 20:
                recent = hist[-20:]
                # Check for monotonic increase (leak signature)
                increasing_count = sum(
                    1 for i in range(1, len(recent)) if recent[i] > recent[i-1]
                )
                if increasing_count >= 16:  # 80%+ of samples increasing
                    growth_rate = (recent[-1] - recent[0]) / len(recent)
                    if growth_rate > 0.5:  # >0.5 MB per sample
                        insights.append({
                            "agent": "memory",
                            "type": "memory_leak",
                            "severity": "warning",
                            "service": svc,
                            "namespace": ns,
                            "message": f"{svc} showing memory leak pattern — {increasing_count}/20 consecutive "
                                       f"increases, growing ~{growth_rate:.1f}MB/interval. "
                                       f"Current: {mem_mb:.0f}MB. Enable heap profiling.",
                            "value": mem_mb,
                            "growth_rate_mb_per_interval": round(growth_rate, 2),
                        })

            # ── Abnormal Growth (sudden spike) ────────────────────────────
            if len(hist) >= 5:
                avg_recent = sum(hist[-5:]) / 5
                avg_older = sum(hist[-10:-5]) / 5 if len(hist) >= 10 else avg_recent
                if avg_older > 0 and avg_recent > avg_older * 1.5:
                    insights.append({
                        "agent": "memory",
                        "type": "memory_spike",
                        "severity": "warning",
                        "service": svc,
                        "namespace": ns,
                        "message": f"{svc} memory jumped from ~{avg_older:.0f}MB to ~{avg_recent:.0f}MB "
                                   f"({((avg_recent/avg_older - 1) * 100):.0f}% increase). "
                                   f"Check for allocation bursts or cache growth.",
                        "value": mem_mb,
                    })

        return insights


memory_agent = MemoryAgent()
