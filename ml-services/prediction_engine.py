"""
KubeMind AI — Prediction Engine
Linear regression + exponential smoothing for failure forecasting.
"""
import numpy as np
from sklearn.linear_model import LinearRegression
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

RISK_THRESHOLDS = {
    "cpu_percent": 90.0,
    "memory_mb": 1500,
    "disk_usage_percent": 95.0,
    "error_rate_percent": 25.0,
    "restart_count": 8,
}


class PredictionEngine:
    def __init__(self):
        self._history: Dict[str, List[Dict]] = {}

    def ingest(self, service: str, metrics: Dict[str, Any]) -> None:
        if service not in self._history:
            self._history[service] = []
        self._history[service].append(metrics)
        if len(self._history[service]) > 300:
            self._history[service].pop(0)

    def predict_failure_probability(self, service: str) -> Dict[str, Any]:
        history = self._history.get(service, [])
        if len(history) < 15:
            return {
                "service": service, "status": "insufficient_data",
                "failure_probability_15m": 0.05, "failure_probability_30m": 0.08,
                "failure_probability_60m": 0.12, "risk_level": "low",
                "risk_factors": [], "top_risk_metric": None,
                "predicted_at": datetime.now(timezone.utc).isoformat(),
            }

        risk_factors = []
        max_risk = 0.0

        for metric, threshold in RISK_THRESHOLDS.items():
            values = [h.get(metric, 0) for h in history]
            if not values:
                continue
            X = np.arange(len(values)).reshape(-1, 1)
            y = np.array(values)
            try:
                model = LinearRegression()
                model.fit(X, y)
                slope = float(model.coef_[0])
                n = len(values)
                steps_15m = int(15 * 60 / 15)
                steps_30m = int(30 * 60 / 15)
                steps_60m = int(60 * 60 / 15)
                pred_15m = float(model.predict([[n + steps_15m]])[0])
                pred_30m = float(model.predict([[n + steps_30m]])[0])
                pred_60m = float(model.predict([[n + steps_60m]])[0])
                current_val = values[-1]
                ratio = current_val / threshold if threshold > 0 else 0
                if ratio > 0.6 or slope > 0.5:
                    risk = min(1.0, ratio * 0.8 + (slope / threshold) * 20)
                    max_risk = max(max_risk, risk)
                    risk_factors.append({
                        "metric": metric, "current": round(current_val, 2),
                        "threshold": threshold, "ratio": round(ratio, 3),
                        "trend": "rising" if slope > 0.1 else "stable",
                        "slope_per_min": round(slope * 4, 4),
                        "predicted_15m": round(pred_15m, 2),
                        "predicted_30m": round(pred_30m, 2),
                        "predicted_60m": round(pred_60m, 2),
                        "breach_expected": pred_60m >= threshold,
                    })
            except Exception:
                pass

        breach_count = len([r for r in risk_factors if r["breach_expected"]])
        fp_15m = min(0.95, max_risk * 0.6 + breach_count * 0.1)
        fp_30m = min(0.95, max_risk * 0.75 + breach_count * 0.15)
        fp_60m = min(0.95, max_risk + breach_count * 0.2)

        return {
            "service": service, "status": "predicted",
            "failure_probability_15m": round(fp_15m, 3),
            "failure_probability_30m": round(fp_30m, 3),
            "failure_probability_60m": round(fp_60m, 3),
            "risk_level": (
                "critical" if fp_30m > 0.7 else "high" if fp_30m > 0.4
                else "medium" if fp_30m > 0.2 else "low"
            ),
            "risk_factors": risk_factors,
            "top_risk_metric": risk_factors[0]["metric"] if risk_factors else None,
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        }


prediction_engine = PredictionEngine()
