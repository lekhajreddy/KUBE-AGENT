"""
KubeMind — Recommendation Engine (Real Kubernetes Edition)
Generates actionable K8s-specific recommendations from anomalies + predictions.
"""
from typing import Any, Dict, List


# Real K8s fault → recommendation mapping
FAULT_RECOMMENDATIONS = {
    "CPU Spike": {
        "type": "Scaling",
        "action": "kubectl scale deployment <name> --replicas=<N> OR increase HPA maxReplicas",
        "priority": "High",
    },
    "Memory Leak": {
        "type": "Maintenance",
        "action": "kubectl rollout restart deployment/<name> — enable heap profiling with JVM/Go pprof",
        "priority": "High",
    },
    "Crash Loop": {
        "type": "Debugging",
        "action": "kubectl logs <pod> --previous — fix liveness probe thresholds or startup probe",
        "priority": "Critical",
    },
    "Network Ingress Surge": {
        "type": "Traffic Management",
        "action": "Apply Ingress rate limiting or HPA scale-out — check for retry storms",
        "priority": "Medium",
    },
    "Network Egress Surge": {
        "type": "Traffic Management",
        "action": "Audit outbound calls — apply NetworkPolicy egress limits",
        "priority": "Medium",
    },
    "Storage Overload": {
        "type": "Capacity",
        "action": "kubectl patch pvc <name> -p '{\"spec\":{\"resources\":{\"requests\":{\"storage\":\"<size>\"}}}}' OR clean stale data",
        "priority": "High",
    },
    "High Error Rate": {
        "type": "Reliability",
        "action": "Implement circuit breaker (Istio / Resilience4j) — audit downstream dependencies",
        "priority": "High",
    },
    "Latency Degradation": {
        "type": "Performance",
        "action": "Profile with kubectl exec + pprof — check DB query plans and connection pool",
        "priority": "Medium",
    },
    "OOMKilled": {
        "type": "Resource Tuning",
        "action": "Increase memory limit: kubectl set resources deployment/<name> --limits=memory=<size>",
        "priority": "Critical",
    },
    "CrashLoopBackOff": {
        "type": "Debugging",
        "action": "kubectl logs <pod> --previous && kubectl describe pod <pod> — fix app startup error",
        "priority": "Critical",
    },
    "PVC Bottleneck": {
        "type": "Storage",
        "action": "Expand PVC capacity or migrate to faster StorageClass (e.g., SSD-backed)",
        "priority": "High",
    },
    "Pod Pending": {
        "type": "Scheduling",
        "action": "Check node resource pressure: kubectl describe node — add worker nodes or reduce requests",
        "priority": "High",
    },
}


class RecommendationEngine:
    def generate(
        self,
        anomaly_data: Dict[str, Any],
        prediction_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        svc = anomaly_data.get("service", "unknown")
        ns  = anomaly_data.get("namespace", "default")

        # ── Anomaly-driven recommendations ─────────────────────────────────
        if anomaly_data.get("is_anomaly"):
            for atype in anomaly_data.get("anomaly_types", []):
                template = FAULT_RECOMMENDATIONS.get(atype)
                if template:
                    action = template["action"].replace("<name>", svc).replace("<pod>", f"{svc}-<hash>")
                    recs.append({
                        "id":       f"{svc}-{atype.lower().replace(' ', '-')}",
                        "service":  svc,
                        "namespace": ns,
                        **template,
                        "action":   action,
                        "reason":   f"{atype} detected via {anomaly_data.get('detection_method', 'ML')}",
                    })

        # ── OOMKilled direct detection ─────────────────────────────────────
        if anomaly_data.get("oom_killed"):
            recs.append({
                "id":       f"{svc}-oomkilled",
                "service":  svc,
                "namespace": ns,
                "type":     "Resource Tuning",
                "action":   f"kubectl set resources deployment/{svc} -n {ns} --limits=memory=512Mi",
                "priority": "Critical",
                "reason":   "Pod was OOMKilled — memory limit exceeded",
            })

        # ── CrashLoop direct detection ─────────────────────────────────────
        if anomaly_data.get("crash_loop"):
            recs.append({
                "id":       f"{svc}-crashloop",
                "service":  svc,
                "namespace": ns,
                "type":     "Debugging",
                "action":   f"kubectl logs {svc} -n {ns} --previous && kubectl describe pod -n {ns} -l app={svc}",
                "priority": "Critical",
                "reason":   "CrashLoopBackOff detected — pod restarting repeatedly",
            })

        # ── High restart count ─────────────────────────────────────────────
        restart_count = anomaly_data.get("restart_count", 0)
        if restart_count >= 5:
            recs.append({
                "id":       f"{svc}-restart-rolling",
                "service":  svc,
                "namespace": ns,
                "type":     "Maintenance",
                "action":   f"kubectl rollout restart deployment/{svc} -n {ns}",
                "priority": "High",
                "reason":   f"Pod has restarted {restart_count} times — rolling restart recommended",
            })

        # ── Prediction-driven pre-emptive recommendations ──────────────────
        risk  = prediction_data.get("risk_level", "low")
        fp30  = prediction_data.get("failure_probability_30m", 0)
        if risk in ("high", "critical"):
            recs.append({
                "id":       f"{svc}-predictive-scale",
                "service":  svc,
                "namespace": ns,
                "type":     "Predictive Scaling",
                "action":   f"kubectl scale deployment/{svc} -n {ns} --replicas=<N+1> before resource exhaustion",
                "priority": "Critical" if risk == "critical" else "High",
                "reason":   f"Predicted failure probability in 30 min: {fp30 * 100:.1f}%",
            })

        top_risk = prediction_data.get("top_risk_metric")
        if top_risk:
            recs.append({
                "id":       f"{svc}-{top_risk}-trend",
                "service":  svc,
                "namespace": ns,
                "type":     "Resource Optimization",
                "action":   f"Review and tune {top_risk} resource requests/limits for {svc}",
                "priority": "Medium",
                "reason":   f"Trend analysis shows rising slope in {top_risk}",
            })

        # ── De-duplicate ────────────────────────────────────────────────────
        seen = set()
        unique_recs = []
        for r in recs:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique_recs.append(r)
        return unique_recs


recommendation_engine = RecommendationEngine()
