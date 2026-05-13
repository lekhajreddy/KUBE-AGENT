import httpx
import logging
from typing import Dict, Any, List
from app.core.config import settings

logger = logging.getLogger(__name__)

async def _post(url: str, json_data: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=json_data)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning(f"Microservice call failed for {url}: {e}")
        return {}

class MLServiceClient:
    async def detect_anomaly(self, service: str, metrics: dict) -> dict:
        payload = {"service": service, **metrics}
        res = await _post(f"{settings.ML_SERVICE_URL}/api/v1/detect", payload)
        if not res:
            return {"service": service, "is_anomaly": False, "anomaly_score": 0, "confidence": 0, "severity": "normal", "anomaly_types": [], "threshold_violations": [], "detection_method": "fallback"}
        return res

    async def predict_failure(self, service: str, metrics: dict) -> dict:
        payload = {"service": service, **metrics}
        res = await _post(f"{settings.ML_SERVICE_URL}/api/v1/predict", payload)
        if not res:
            return {"service": service, "status": "unavailable", "failure_probability_15m": 0, "failure_probability_30m": 0, "failure_probability_60m": 0, "risk_level": "low", "risk_factors": []}
        return res

class AIServiceClient:
    async def perform_rca(self, anomalies: list, metrics: list, topology: dict = None) -> list:
        res = await _post(f"{settings.AI_SERVICE_URL}/api/v1/rca", {
            "anomalies": anomalies, 
            "metrics": metrics,
            "topology": topology
        })
        return res if isinstance(res, list) else []

    async def get_recommendations(self, anomaly: dict, prediction: dict) -> list:
        res = await _post(f"{settings.AI_SERVICE_URL}/api/v1/recommend", {"anomaly": anomaly, "prediction": prediction})
        return res if isinstance(res, list) else []

    async def ai_query(self, query: str, context: str) -> dict:
        res = await _post(f"{settings.AI_SERVICE_URL}/api/v1/query", {"query": query, "context": context})
        return res if res else {"response": "AI engine unavailable.", "source": "fallback"}

ml_client = MLServiceClient()
ai_client = AIServiceClient()
