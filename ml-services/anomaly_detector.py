"""
KubeMind — ML Anomaly Detector (Real Kubernetes Edition)
Isolation Forest + threshold detection tuned for real K8s workloads.
Detects: CrashLoopBackOff, OOMKilled, high CPU/memory, PVC pressure, probe failures.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "cpu_percent", "memory_mb", "network_in_kbps",
    "network_out_kbps", "pvc_usage_percent",
    "restart_count",
]

ANOMALY_LABELS = {
    "cpu_percent":        "CPU Spike",
    "memory_mb":          "Memory Leak",
    "network_in_kbps":    "Network Ingress Surge",
    "network_out_kbps":   "Network Egress Surge",
    "pvc_usage_percent":  "PVC Bottleneck",
    "restart_count":      "Crash Loop",
}

# Real K8s thresholds — tuned for actual cluster workloads
SEVERITY_THRESHOLDS = {
    "cpu_percent":        {"warning": 70,  "critical": 90},
    "memory_mb":          {"warning": 700, "critical": 1200},
    "network_in_kbps":    {"warning": 5000, "critical": 15000},
    "network_out_kbps":   {"warning": 3000, "critical": 10000},
    "pvc_usage_percent":  {"warning": 80,  "critical": 95},
    "restart_count":      {"warning": 3,   "critical": 5},
}


class AnomalyDetector:
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.models:      Dict[str, IsolationForest]  = {}
        self.scalers:     Dict[str, StandardScaler]   = {}
        self.is_trained:  Dict[str, bool]             = {}
        self._history_buffer: Dict[str, List[Dict]]   = {}

    def ingest(self, service: str, metrics: Dict[str, Any]) -> None:
        if service not in self._history_buffer:
            self._history_buffer[service] = []
        self._history_buffer[service].append(metrics)
        if len(self._history_buffer[service]) > 200:
            self._history_buffer[service].pop(0)

    def _train(self, service: str) -> bool:
        history = self._history_buffer.get(service, [])
        if len(history) < 15:   # lower threshold for real K8s (less data points)
            return False
        df = pd.DataFrame(history)
        available_cols = [c for c in FEATURE_COLS if c in df.columns]
        if not available_cols:
            return False
        X = df[available_cols].fillna(0).values
        scaler  = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_scaled)
        self.models[service]    = model
        self.scalers[service]   = scaler
        self.is_trained[service] = True
        return True

    def detect(self, service: str, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        self.ingest(service, current_metrics)

        # Always run threshold detection for real K8s conditions
        threshold_result = self._threshold_detect(service, current_metrics)

        # Check for hard K8s failure states directly
        hard_anomaly = self._detect_k8s_hard_states(service, current_metrics)
        if hard_anomaly:
            # Merge hard state with threshold result
            threshold_result["is_anomaly"]    = True
            threshold_result["severity"]      = "critical"
            threshold_result["anomaly_types"] = list(set(
                threshold_result.get("anomaly_types", []) + hard_anomaly
            ))
            threshold_result["detection_method"] = "k8s-state"
            return threshold_result

        # If not enough history, return threshold-only
        if not self.is_trained.get(service):
            if not self._train(service):
                return threshold_result

        available_cols = [c for c in FEATURE_COLS if c in current_metrics]
        if not available_cols:
            return threshold_result

        values = np.array([[current_metrics.get(c, 0) for c in available_cols]])
        try:
            X_scaled   = self.scalers[service].transform(values)
            score      = self.models[service].score_samples(X_scaled)[0]
            prediction = self.models[service].predict(X_scaled)[0]
            is_ml_anomaly  = bool(prediction == -1)
            confidence = float(min(1.0, max(0.0, (0.0 - score) / 0.5)))
        except Exception as e:
            logger.warning(f"ML inference failed for {service}: {e}")
            return threshold_result

        anomaly_types = self._identify_anomaly_types(current_metrics)
        severity      = self._compute_severity(current_metrics)

        # Combine ML result with threshold result
        is_anomaly = is_ml_anomaly or threshold_result["is_anomaly"]

        return {
            "service":            service,
            "timestamp":          datetime.now(timezone.utc).isoformat(),
            "is_anomaly":         is_anomaly,
            "anomaly_score":      round(float(score), 4),
            "confidence":         round(confidence, 3),
            "severity":           severity if is_anomaly else "normal",
            "anomaly_types":      anomaly_types if is_anomaly else [],
            "detection_method":   "isolation_forest+threshold",
            "threshold_violations": self._get_threshold_violations(current_metrics),
            # Pass through real K8s fields
            "crash_loop":  current_metrics.get("crash_loop", False),
            "oom_killed":  current_metrics.get("oom_killed", False),
            "restart_count": current_metrics.get("restart_count", 0),
            "namespace":   current_metrics.get("namespace", ""),
        }

    def _detect_k8s_hard_states(self, service: str, metrics: Dict) -> List[str]:
        """Detect direct K8s failure states regardless of ML model."""
        types = []
        if metrics.get("crash_loop"):
            types.append("CrashLoopBackOff")
        if metrics.get("oom_killed"):
            types.append("OOMKilled")
        status = metrics.get("status", "")
        phase  = metrics.get("phase", "")
        if status == "CrashLoopBackOff" or "CrashLoop" in status:
            if "CrashLoopBackOff" not in types:
                types.append("CrashLoopBackOff")
        if phase in ("Failed", "Unknown"):
            types.append(f"Pod {phase}")
        if status == "OOMKilled":
            if "OOMKilled" not in types:
                types.append("OOMKilled")
        if metrics.get("pvc_usage_percent", 0) >= SEVERITY_THRESHOLDS["pvc_usage_percent"]["critical"]:
            types.append("PVC Bottleneck")
        return types

    def _threshold_detect(self, service: str, metrics: Dict) -> Dict:
        violations = self._get_threshold_violations(metrics)
        is_anomaly = len(violations) > 0
        severity   = self._compute_severity(metrics)
        return {
            "service":            service,
            "timestamp":          datetime.now(timezone.utc).isoformat(),
            "is_anomaly":         is_anomaly,
            "anomaly_score":      -0.3 if is_anomaly else 0.1,
            "confidence":         0.7 if is_anomaly else 0.0,
            "severity":           severity if is_anomaly else "normal",
            "anomaly_types":      [v["type"] for v in violations],
            "detection_method":   "threshold",
            "threshold_violations": violations,
            "crash_loop":  metrics.get("crash_loop", False),
            "oom_killed":  metrics.get("oom_killed", False),
            "restart_count": metrics.get("restart_count", 0),
            "namespace":   metrics.get("namespace", ""),
        }

    def _get_threshold_violations(self, metrics: Dict) -> List[Dict]:
        violations = []
        for col, thresholds in SEVERITY_THRESHOLDS.items():
            val = metrics.get(col, 0)
            if val is None:
                continue
            if val >= thresholds["critical"]:
                violations.append({
                    "metric":    col,
                    "type":      ANOMALY_LABELS.get(col, col),
                    "value":     val,
                    "threshold": thresholds["critical"],
                    "severity":  "critical",
                })
            elif val >= thresholds["warning"]:
                violations.append({
                    "metric":    col,
                    "type":      ANOMALY_LABELS.get(col, col),
                    "value":     val,
                    "threshold": thresholds["warning"],
                    "severity":  "warning",
                })
        return violations

    def _identify_anomaly_types(self, metrics: Dict) -> List[str]:
        return list({v["type"] for v in self._get_threshold_violations(metrics)})

    def _compute_severity(self, metrics: Dict) -> str:
        # Hard K8s failures are always critical
        if metrics.get("crash_loop") or metrics.get("oom_killed"):
            return "critical"
        violations = self._get_threshold_violations(metrics)
        if any(v["severity"] == "critical" for v in violations):
            return "critical"
        if violations:
            return "warning"
        return "normal"


anomaly_detector = AnomalyDetector(contamination=0.1)
