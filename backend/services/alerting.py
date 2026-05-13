"""
KubeMind — Alerting Engine
Multi-channel alerting with Slack, Discord, Email, and Webhooks.
Rule-based alert evaluation with deduplication and escalation.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

import httpx

logger = logging.getLogger("kubemind.alerting")


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"
    WEBHOOK = "webhook"


class AlertRule:
    def __init__(self, name: str, metric: str, threshold: float,
                 duration_seconds: int = 300, severity: AlertSeverity = AlertSeverity.WARNING,
                 description: str = "", channel: AlertChannel = AlertChannel.WEBHOOK,
                 enabled: bool = True):
        self.name = name
        self.metric = metric
        self.threshold = threshold
        self.duration_seconds = duration_seconds
        self.severity = severity
        self.description = description or f"{metric} exceeds {threshold}"
        self.channel = channel
        self.enabled = enabled


DEFAULT_RULES = [
    AlertRule("cpu_critical", "cpu_percent", 90, 300, AlertSeverity.CRITICAL,
              "CPU usage above 90% for 5 minutes"),
    AlertRule("cpu_warning", "cpu_percent", 70, 300, AlertSeverity.WARNING,
              "CPU usage above 70% for 5 minutes"),
    AlertRule("memory_critical", "memory_mb", 1000, 300, AlertSeverity.CRITICAL,
              "Memory usage above 1000MB"),
    AlertRule("memory_warning", "memory_mb", 700, 300, AlertSeverity.WARNING,
              "Memory usage above 700MB"),
    AlertRule("restart_critical", "restart_count", 5, 60, AlertSeverity.CRITICAL,
              "Pod restart count above 5"),
    AlertRule("restart_warning", "restart_count", 3, 60, AlertSeverity.WARNING,
              "Pod restart count above 3"),
    AlertRule("pvc_critical", "pvc_usage_percent", 95, 300, AlertSeverity.CRITICAL,
              "PVC usage above 95%"),
    AlertRule("pvc_warning", "pvc_usage_percent", 80, 300, AlertSeverity.WARNING,
              "PVC usage above 80%"),
]


class AlertEngine:
    def __init__(self):
        self._rules: List[AlertRule] = DEFAULT_RULES[:]
        self._cooldown: Dict[str, float] = {}
        self._cooldown_seconds: int = 300
        self._alert_history: List[dict] = []
        self._max_history: int = 1000
        self._listeners: List[Callable] = []
        self._channels: Dict[AlertChannel, Dict] = {}

    def configure_channel(self, channel: AlertChannel, config: dict):
        self._channels[channel] = config

    def register_listener(self, callback: Callable):
        self._listeners.append(callback)

    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)

    def remove_rule(self, name: str):
        self._rules = [r for r in self._rules if r.name != name]

    async def evaluate_metrics(self, metrics: List[dict]) -> List[dict]:
        fired = []
        now = time.time()

        for m in metrics:
            svc = m.get("service", "unknown")
            ns = m.get("namespace", "unknown")

            for rule in self._rules:
                if not rule.enabled:
                    continue

                metric_val = m.get(rule.metric, 0)
                if metric_val is None:
                    continue

                if metric_val >= rule.threshold:
                    alert_key = f"{rule.name}/{ns}/{svc}"
                    last_fired = self._cooldown.get(alert_key, 0)

                    if now - last_fired >= self._cooldown_seconds:
                        alert = {
                            "id": alert_key,
                            "rule": rule.name,
                            "severity": rule.severity.value,
                            "metric": rule.metric,
                            "value": round(float(metric_val), 2),
                            "threshold": rule.threshold,
                            "service": svc,
                            "namespace": ns,
                            "description": rule.description,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "fired_at": now,
                        }
                        fired.append(alert)
                        self._cooldown[alert_key] = now
                        self._alert_history.append(alert)
                        if len(self._alert_history) > self._max_history:
                            self._alert_history.pop(0)

                        for listener in self._listeners:
                            try:
                                if asyncio.iscoroutinefunction(listener):
                                    await listener(alert)
                                else:
                                    listener(alert)
                            except Exception as e:
                                logger.error(f"Alert listener error: {e}")

                        await self._dispatch(alert)

        return fired

    async def _dispatch(self, alert: dict):
        tasks = []
        for channel, config in self._channels.items():
            tasks.append(self._send(alert, channel, config))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send(self, alert: dict, channel: AlertChannel, config: dict):
        try:
            if channel == AlertChannel.SLACK:
                await self._send_slack(alert, config)
            elif channel == AlertChannel.DISCORD:
                await self._send_discord(alert, config)
            elif channel == AlertChannel.EMAIL:
                await self._send_email(alert, config)
            elif channel == AlertChannel.WEBHOOK:
                await self._send_webhook(alert, config)
        except Exception as e:
            logger.error(f"Alert send failed for {channel}: {e}")

    async def _send_slack(self, alert: dict, config: dict):
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            return
        color = {"critical": "danger", "warning": "warning", "info": "good"}.get(alert["severity"], "good")
        payload = {
            "attachments": [{
                "color": color,
                "title": f"[{alert['severity'].upper()}] {alert['rule']}",
                "text": (
                    f"*Service:* {alert['service']}\n"
                    f"*Namespace:* {alert['namespace']}\n"
                    f"*Metric:* {alert['metric']}\n"
                    f"*Value:* {alert['value']} (threshold: {alert['threshold']})\n"
                    f"*Description:* {alert['description']}"
                ),
                "footer": "KubeMind AI Observability",
                "ts": int(alert.get("fired_at", time.time())),
            }]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json=payload)

    async def _send_discord(self, alert: dict, config: dict):
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            return
        color_map = {"critical": 15548997, "warning": 16776960, "info": 5814783}
        payload = {
            "embeds": [{
                "title": f"[{alert['severity'].upper()}] {alert['rule']}",
                "color": color_map.get(alert["severity"], 5814783),
                "fields": [
                    {"name": "Service", "value": alert["service"], "inline": True},
                    {"name": "Namespace", "value": alert["namespace"], "inline": True},
                    {"name": "Metric", "value": f"{alert['metric']} = {alert['value']} (threshold: {alert['threshold']})", "inline": False},
                    {"name": "Description", "value": alert["description"], "inline": False},
                ],
                "footer": {"text": "KubeMind AI Observability"},
                "timestamp": alert["timestamp"],
            }]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json=payload)

    async def _send_email(self, alert: dict, config: dict):
        smtp_host = config.get("smtp_host", "")
        smtp_port = config.get("smtp_port", 587)
        username = config.get("username", "")
        password = config.get("password", "")
        to = config.get("to", "")
        from_addr = config.get("from", "alerts@kubemind.ai")

        if not all([smtp_host, to]):
            return

        import aiosmtplib
        from email.mime.text import MIMEText

        body = f"""
KubeMind Alert: {alert['rule']}

Severity: {alert['severity'].upper()}
Service: {alert['service']}
Namespace: {alert['namespace']}
Metric: {alert['metric']} = {alert['value']} (threshold: {alert['threshold']})
Description: {alert['description']}
Time: {alert['timestamp']}

---
KubeMind AI Observability Platform
"""
        msg = MIMEText(body, "plain")
        msg["Subject"] = f"[{alert['severity'].upper()}] KubeMind Alert: {alert['rule']}"
        msg["From"] = from_addr
        msg["To"] = to

        try:
            async with aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port) as smtp:
                if username and password:
                    await smtp.login(username, password)
                await smtp.send_message(msg)
                logger.info(f"Alert email sent to {to}")
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    async def _send_webhook(self, alert: dict, config: dict):
        webhook_url = config.get("url", "")
        if not webhook_url:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json=alert)

    def get_recent_alerts(self, limit: int = 50) -> List[dict]:
        return list(reversed(self._alert_history[-limit:]))

    def get_active_alerts(self, within_seconds: int = 3600) -> List[dict]:
        now = time.time()
        return [a for a in self._alert_history if now - a.get("fired_at", 0) <= within_seconds]


alert_engine = AlertEngine()
