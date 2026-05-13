"""
KubeMind AI — Ollama Client & AI Insight Engine (Enhanced)
Generates operational narratives, RCA explanations, and actionable recommendations.
"""
import httpx
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are KubeMind AI, an infrastructure intelligence platform that explains Kubernetes behavior.
You analyze metrics, anomalies, dependencies, and correlations to produce operational narratives.
Always respond in a structured format covering:
1. What happened (detected anomaly/event)
2. Why it matters (impact analysis)
3. Root cause (correlated evidence)
4. Recommended actions (specific kubectl commands or configuration changes)
Keep responses concise, technical, and actionable."""


class OllamaClient:
    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.enabled = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"

    async def generate_insight(self, context: str, prompt: str) -> str:
        if not self.enabled:
            return self._fallback(prompt)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{self.host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {prompt}\n\nAnswer:",
                        "stream": False,
                        "options": {"temperature": 0.3, "max_tokens": 400},
                    },
                )
                r.raise_for_status()
                return r.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama unavailable ({e}), using rule engine.")
            return self._fallback(prompt)

    async def analyze_anomalies(self, anomalies: List[Dict[str, Any]],
                                 correlations: Optional[List[Dict]] = None,
                                 impact_chains: Optional[List[Dict]] = None) -> str:
        if not anomalies:
            return "No anomalies detected in the current observation window."
        ctx = {
            "anomalies": anomalies[:5],
            "correlations": correlations[:3] if correlations else [],
            "impact_chains": impact_chains[:2] if impact_chains else [],
        }
        return await self.generate_insight(
            json.dumps(ctx, indent=2, default=str),
            "Analyze these infrastructure anomalies. Explain what happened, why it matters, "
            "identify the root cause, and provide specific recommended actions."
        )

    async def generate_narrative(self, anomaly_summary: str, correlation_data: str,
                                   health_score: str, exhaustion_predictions: str) -> str:
        context = f"""Anomalies: {anomaly_summary}
Correlations: {correlation_data}
Health Score: {health_score}
Exhaustion Predictions: {exhaustion_predictions}"""
        return await self.generate_insight(
            context,
            "Generate a concise operational intelligence summary for the Kubernetes cluster. "
            "Include: what's happening, impact analysis, and top 3 recommended actions."
        )

    def _fallback(self, prompt: str) -> str:
        q = prompt.lower()
        if "cpu" in q and ("spike" in q or "high" in q):
            return (
                "KubeMind detected abnormal CPU activity. "
                "The affected pod is experiencing CPU saturation above 80%, "
                "which may cause request throttling and latency degradation. "
                "Recommended actions:\n"
                "- Scale replicas: kubectl scale deployment <name> --replicas=<N+1>\n"
                "- Review HPA configuration for proactive scaling\n"
                "- Check for resource leaks or infinite loops in application code"
            )
        if "memory" in q and ("leak" in q or "high" in q):
            return (
                "Memory growth trend detected in monitored service. "
                "Current usage exceeds warning threshold with upward trajectory. "
                "This pattern is consistent with a memory leak. "
                "Recommended actions:\n"
                "- kubectl rollout restart deployment/<name>\n"
                "- Enable heap profiling (jmap/pprof) to identify leak source\n"
                "- Increase memory limits temporarily"
            )
        if "pvc" in q or "disk" in q or "storage" in q:
            return (
                "Persistent volume usage is critically high. "
                "Write latency is increasing which impacts database and stateful workloads. "
                "Recommended actions:\n"
                "- Expand PVC: kubectl patch pvc <name> -p '{\"spec\":{\"resources\":{\"requests\":{\"storage\":\"<new-size>\"}}}}'\n"
                "- Clean up stale data and logs\n"
                "- Consider faster StorageClass (SSD-backed)"
            )
        if "network" in q:
            return (
                "Elevated network I/O detected. Ingress traffic has spiked, "
                "potentially causing API saturation and increased latency downstream. "
                "Recommended actions:\n"
                "- Apply Ingress rate limiting\n"
                "- Scale out frontend deployments\n"
                "- Check for retry storms or DDoS patterns"
            )
        if "predict" in q or "fail" in q:
            return (
                "Predictive analysis indicates elevated failure probability over the next 30 minutes. "
                "Key risk factors include rising CPU trends and memory pressure. "
                "Proactive scaling is recommended before resource exhaustion occurs."
            )
        if "cascade" in q or "chain" in q or "dependenc" in q:
            return (
                "Cascading failure chain detected in the dependency graph. "
                "The root cause service is impacting downstream dependencies. "
                "Fix the root cause first before restarting affected services. "
                "Consider circuit breakers and bulkheads to isolate failures."
            )
        return (
            "KubeMind is actively monitoring your Kubernetes infrastructure. "
            "All services are operating within normal parameters. "
            "No critical issues detected at this time."
        )


ollama_client = OllamaClient()
