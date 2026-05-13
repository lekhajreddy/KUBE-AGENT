"""
KubeMind — Correlation Intelligence Engine
Cross-metric reasoning with Pearson correlation, sliding windows, and spike detection.
Discovers relationships between CPU, memory, network, PVC, and restart events.
"""
import logging
import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kubemind.correlation")

METRIC_PAIRS = [
    ("cpu_percent", "restart_count", "CPU spike → pod throttling → restart"),
    ("cpu_percent", "memory_mb", "CPU spike → memory pressure"),
    ("pvc_usage_percent", "memory_mb", "High disk I/O → cache pressure → memory increase"),
    ("network_in_kbps", "cpu_percent", "Traffic burst → API saturation"),
    ("network_out_kbps", "cpu_percent", "Egress surge → CPU processing"),
    ("latency_ms", "cpu_percent", "Latency increase → CPU saturation"),
    ("memory_mb", "restart_count", "Memory pressure → OOM risk → restart"),
    ("pvc_usage_percent", "latency_ms", "PVC overload → I/O wait → latency"),
]

SPIKE_THRESHOLDS = {
    "cpu_percent": {"warning": 70, "critical": 90},
    "memory_mb": {"warning": 600, "critical": 1000},
    "pvc_usage_percent": {"warning": 75, "critical": 90},
    "network_in_kbps": {"warning": 8000, "critical": 15000},
    "network_out_kbps": {"warning": 5000, "critical": 10000},
    "latency_ms": {"warning": 200, "critical": 500},
    "restart_count": {"warning": 3, "critical": 6},
}


class CorrelationEngine:
    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self._history: Dict[str, Dict[str, List[float]]] = {}
        self._correlation_cache: Dict[str, Dict[str, float]] = {}
        self._spike_history: Dict[str, List[Dict]] = {}
        self._correlation_results: List[Dict] = []

    def ingest(self, service: str, metrics: Dict[str, Any]) -> None:
        ts = time.time()
        if service not in self._history:
            self._history[service] = defaultdict(list)
            self._spike_history[service] = []
        for key in METRIC_PAIRS:
            m1, m2, _ = key
            val1 = metrics.get(m1, 0) or 0
            val2 = metrics.get(m2, 0) or 0
            self._history[service][m1].append((ts, val1))
            self._history[service][m2].append((ts, val2))
            if len(self._history[service][m1]) > self.window_size:
                self._history[service][m1].pop(0)
                self._history[service][m2].pop(0)
        spike = self._detect_spike(service, metrics)
        if spike:
            self._spike_history[service].append(spike)
        if len(self._spike_history[service]) > 50:
            self._spike_history[service].pop(0)

    def _detect_spike(self, service: str, metrics: Dict[str, Any]) -> Optional[Dict]:
        spikes = []
        for metric, thresholds in SPIKE_THRESHOLDS.items():
            val = metrics.get(metric, 0) or 0
            if val >= thresholds["critical"]:
                spikes.append({"metric": metric, "value": val, "severity": "critical", "threshold": thresholds["critical"]})
            elif val >= thresholds["warning"]:
                spikes.append({"metric": metric, "value": val, "severity": "warning", "threshold": thresholds["warning"]})
        if spikes:
            return {"ts": time.time(), "service": service, "spikes": spikes}
        return None

    def _pearson(self, xs: List[float], ys: List[float]) -> float:
        n = len(xs)
        if n < 5:
            return 0.0
        sx = sum(xs)
        sy = sum(ys)
        sxx = sum(x * x for x in xs)
        syy = sum(y * y for y in ys)
        sxy = sum(x * y for x, y in zip(xs, ys))
        num = n * sxy - sx * sy
        denom = (n * sxx - sx * sx) * (n * syy - sy * sy)
        if denom <= 0:
            return 0.0
        den = math.sqrt(denom)
        if den == 0:
            return 0.0
        r = num / den
        return max(-1.0, min(1.0, r))

    def _compute_correlations(self, service: str) -> List[Dict]:
        results = []
        hist = self._history.get(service, {})
        for m1, m2, label in METRIC_PAIRS:
            s1 = hist.get(m1, [])
            s2 = hist.get(m2, [])
            n = min(len(s1), len(s2))
            if n < 5:
                continue
            xs = [s1[i][1] for i in range(n)]
            ys = [s2[i][1] for i in range(n)]
            r = self._pearson(xs, ys)
            if abs(r) >= 0.3:
                results.append({
                    "service": service,
                    "metric_a": m1,
                    "metric_b": m2,
                    "correlation": round(r, 3),
                    "strength": "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.5 else "weak",
                    "direction": "positive" if r > 0 else "negative",
                    "interpretation": label,
                })
        return results

    def analyze(self, metrics: List[Dict], anomalies: List[Dict]) -> Dict[str, Any]:
        for m in metrics:
            self.ingest(m["service"], m)
        all_correlations = []
        services_seen = set()
        for m in metrics:
            svc = m["service"]
            if svc in services_seen:
                continue
            services_seen.add(svc)
            corrs = self._compute_correlations(svc)
            all_correlations.extend(corrs)
        spike_analysis = self._analyze_spike_patterns(anomalies)
        chain_analysis = self._detect_impact_chains(metrics, anomalies)
        return {
            "correlations": all_correlations[:20],
            "spike_analysis": spike_analysis,
            "impact_chains": chain_analysis,
            "active_metric_pairs": [{"metric_a": m1, "metric_b": m2, "label": lbl}
                                     for m1, m2, lbl in METRIC_PAIRS],
        }

    def _analyze_spike_patterns(self, anomalies: List[Dict]) -> List[Dict]:
        patterns = []
        for a in anomalies:
            svc = a.get("service", "")
            spike_records = [s for s in self._spike_history.get(svc, [])]
            recent = spike_records[-5:] if spike_records else []
            for s in recent:
                for sp in s.get("spikes", []):
                    patterns.append({
                        "service": svc,
                        "metric": sp["metric"],
                        "value": sp["value"],
                        "severity": sp["severity"],
                        "detected_at": s["ts"],
                    })
        return patterns[-20:] if patterns else []

    def _detect_impact_chains(self, metrics: List[Dict], anomalies: List[Dict]) -> List[Dict]:
        chains = []
        anomaly_services = {a.get("service", "") for a in anomalies}
        ns_groups = defaultdict(list)
        for m in metrics:
            ns_groups[m["namespace"]].append(m)
        for ns, group in ns_groups.items():
            chain = []
            for m in group:
                svc = m["service"]
                cpu = m.get("cpu_percent", 0) or 0
                mem = m.get("memory_mb", 0) or 0
                pvc = m.get("pvc_usage_percent", 0) or 0
                net = m.get("network_in_kbps", 0) or 0
                lat = m.get("latency_ms", 0) or 0
                score = 0
                triggers = []
                if cpu >= 80:
                    score += 3
                    triggers.append("cpu_saturation")
                if mem >= 800:
                    score += 2
                    triggers.append("memory_pressure")
                if pvc >= 80:
                    score += 3
                    triggers.append("pvc_overload")
                if net >= 10000:
                    score += 2
                    triggers.append("network_burst")
                if lat >= 300:
                    score += 2
                    triggers.append("latency_spike")
                if score > 0:
                    chain.append({
                        "service": svc,
                        "impact_score": score,
                        "triggers": triggers,
                        "is_anomaly": svc in anomaly_services,
                    })
            if len(chain) >= 2:
                chain.sort(key=lambda x: x["impact_score"], reverse=True)
                chains.append({
                    "namespace": ns,
                    "chain": chain,
                    "total_impact": sum(c["impact_score"] for c in chain),
                    "anomaly_count": sum(1 for c in chain if c["is_anomaly"]),
                })
        return sorted(chains, key=lambda c: c["total_impact"], reverse=True)[:5]

    def get_health_score(self, metrics: List[Dict]) -> Dict[str, Any]:
        if not metrics:
            return {"score": 100, "level": "healthy", "factors": []}
        deductions = []
        total = len(metrics)
        cpu_high = sum(1 for m in metrics if (m.get("cpu_percent", 0) or 0) >= 80)
        mem_high = sum(1 for m in metrics if (m.get("memory_mb", 0) or 0) >= 800)
        pvc_high = sum(1 for m in metrics if (m.get("pvc_usage_percent", 0) or 0) >= 80)
        restart_pods = sum(1 for m in metrics if (m.get("restart_count", 0) or 0) >= 3)
        crash_pods = sum(1 for m in metrics if m.get("crash_loop") or m.get("oom_killed"))
        if total > 0:
            cpu_deduction = (cpu_high / total) * 25
            mem_deduction = (mem_high / total) * 20
            pvc_deduction = (pvc_high / total) * 20
            restart_deduction = min(restart_pods * 5, 20)
            crash_deduction = min(crash_pods * 10, 30)
            deductions = [
                {"factor": "High CPU", "deduction": round(cpu_deduction, 1), "count": cpu_high},
                {"factor": "High Memory", "deduction": round(mem_deduction, 1), "count": mem_high},
                {"factor": "PVC Pressure", "deduction": round(pvc_deduction, 1), "count": pvc_high},
                {"factor": "Pod Restarts", "deduction": round(restart_deduction, 1), "count": restart_pods},
                {"factor": "Crash/OOM", "deduction": round(crash_deduction, 1), "count": crash_pods},
            ]
        total_deduction = sum(d["deduction"] for d in deductions)
        score = max(0, min(100, 100 - total_deduction))
        level = "healthy" if score >= 80 else "degraded" if score >= 50 else "critical"
        return {"score": round(score, 1), "level": level, "factors": deductions}

    def get_exhaustion_predictions(self, metrics: List[Dict]) -> List[Dict]:
        predictions = []
        for m in metrics:
            svc = m["service"]
            hist = self._history.get(svc, {})
            for metric, thresholds in SPIKE_THRESHOLDS.items():
                values = [v[1] for v in hist.get(metric, [])]
                if len(values) < 10:
                    continue
                recent = values[-10:]
                avg = sum(recent) / len(recent)
                if len(recent) >= 3:
                    slope = (recent[-1] - recent[0]) / len(recent)
                else:
                    slope = 0
                if slope > 0 and avg > 0:
                    critical = thresholds["critical"]
                    if slope > 0.01:
                        steps_to_critical = (critical - avg) / slope
                        if steps_to_critical > 0 and steps_to_critical < 100:
                            eta_minutes = int(steps_to_critical * 3)
                            predictions.append({
                                "service": svc,
                                "metric": metric,
                                "current_value": round(avg, 1),
                                "threshold": critical,
                                "slope": round(slope, 3),
                                "eta_minutes": eta_minutes,
                                "eta_human": f"{eta_minutes // 60}h {eta_minutes % 60}m" if eta_minutes >= 60 else f"{eta_minutes}m",
                                "severity": "critical" if eta_minutes <= 30 else "warning" if eta_minutes <= 120 else "info",
                            })
        return sorted(predictions, key=lambda p: p["eta_minutes"])[:10]


correlation_engine = CorrelationEngine()
