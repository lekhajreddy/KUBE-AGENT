"""
KubeMind — Multi-Channel Alerting Engine
Sends alerts via Slack, Discord, Email, and generic Webhooks.
Includes deduplication and cooldown to prevent alert storms.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from app.core.config import settings

logger = logging.getLogger("kubemind.alerting")

# ── Alert deduplication ───────────────────────────────────────────────────────
_recent_alerts: Dict[str, float] = {}  # key → timestamp of last fire


def _dedup_key(alert: Dict) -> str:
    return f"{alert.get('service', '')}:{alert.get('alert_type', '')}:{alert.get('severity', '')}"


def _should_send(alert: Dict) -> bool:
    key = _dedup_key(alert)
    now = time.time()
    last = _recent_alerts.get(key, 0)
    if now - last < settings.ALERT_COOLDOWN_SECONDS:
        return False
    _recent_alerts[key] = now
    return True


# ── Alert creation ────────────────────────────────────────────────────────────
def create_alert(
    service: str,
    alert_type: str,
    severity: str,
    message: str,
    namespace: str = "",
    cluster_id: str = "default",
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    return {
        "service": service,
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "namespace": namespace,
        "cluster_id": cluster_id,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resolved": False,
    }


# ── Slack ─────────────────────────────────────────────────────────────────────
async def _send_slack(alert: Dict):
    webhook = settings.ALERT_SLACK_WEBHOOK
    if not webhook:
        return
    severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert["severity"], "⚪")
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{severity_emoji} KubeMind Alert: {alert['alert_type']}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Service:*\n{alert['service']}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{alert['severity'].upper()}"},
                    {"type": "mrkdwn", "text": f"*Namespace:*\n{alert.get('namespace', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Cluster:*\n{alert.get('cluster_id', 'default')}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": alert["message"]},
            },
        ]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"Slack alert failed: {resp.status}")
    except Exception as e:
        logger.error(f"Slack alert error: {e}")


# ── Discord ───────────────────────────────────────────────────────────────────
async def _send_discord(alert: Dict):
    webhook = settings.ALERT_DISCORD_WEBHOOK
    if not webhook:
        return
    color_map = {"critical": 0xFF0000, "warning": 0xFFAA00, "info": 0x00AAFF}
    payload = {
        "embeds": [{
            "title": f"⚡ KubeMind Alert: {alert['alert_type']}",
            "description": alert["message"],
            "color": color_map.get(alert["severity"], 0x888888),
            "fields": [
                {"name": "Service", "value": alert["service"], "inline": True},
                {"name": "Severity", "value": alert["severity"].upper(), "inline": True},
                {"name": "Namespace", "value": alert.get("namespace", "N/A"), "inline": True},
                {"name": "Cluster", "value": alert.get("cluster_id", "default"), "inline": True},
            ],
            "timestamp": alert["timestamp"],
        }]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status not in (200, 204):
                    logger.warning(f"Discord alert failed: {resp.status}")
    except Exception as e:
        logger.error(f"Discord alert error: {e}")


# ── Email ─────────────────────────────────────────────────────────────────────
async def _send_email(alert: Dict):
    if not settings.ALERT_EMAIL_SMTP_HOST or not settings.ALERT_EMAIL_TO:
        return
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[KubeMind {alert['severity'].upper()}] {alert['alert_type']} — {alert['service']}"
        msg["From"] = settings.ALERT_EMAIL_FROM
        msg["To"] = settings.ALERT_EMAIL_TO

        html = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; background: #0f172a; color: #e2e8f0; padding: 24px; border-radius: 12px;">
            <h2 style="color: {'#ef4444' if alert['severity'] == 'critical' else '#f59e0b'};">
                ⚡ KubeMind Alert: {alert['alert_type']}
            </h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px; color: #94a3b8;">Service</td><td style="padding: 8px; font-weight: bold;">{alert['service']}</td></tr>
                <tr><td style="padding: 8px; color: #94a3b8;">Severity</td><td style="padding: 8px; font-weight: bold;">{alert['severity'].upper()}</td></tr>
                <tr><td style="padding: 8px; color: #94a3b8;">Namespace</td><td style="padding: 8px;">{alert.get('namespace', 'N/A')}</td></tr>
                <tr><td style="padding: 8px; color: #94a3b8;">Cluster</td><td style="padding: 8px;">{alert.get('cluster_id', 'default')}</td></tr>
            </table>
            <p style="background: #1e293b; padding: 16px; border-radius: 8px; border-left: 4px solid {'#ef4444' if alert['severity'] == 'critical' else '#f59e0b'};">
                {alert['message']}
            </p>
            <p style="color: #64748b; font-size: 12px; margin-top: 16px;">
                Sent by KubeMind AI at {alert['timestamp']}
            </p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.ALERT_EMAIL_SMTP_HOST,
            port=settings.ALERT_EMAIL_SMTP_PORT,
            username=settings.ALERT_EMAIL_FROM,
            password=settings.ALERT_EMAIL_PASSWORD,
            use_tls=True,
        )
    except Exception as e:
        logger.error(f"Email alert error: {e}")


# ── Generic Webhook ───────────────────────────────────────────────────────────
async def _send_webhook(alert: Dict):
    webhook = settings.ALERT_WEBHOOK_URL
    if not webhook:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=alert, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status >= 400:
                    logger.warning(f"Webhook alert failed: {resp.status}")
    except Exception as e:
        logger.error(f"Webhook alert error: {e}")


# ── Main dispatch ─────────────────────────────────────────────────────────────
async def fire_alert(alert: Dict):
    """Send alert through all configured channels (with deduplication)."""
    if not _should_send(alert):
        logger.debug(f"Alert suppressed (cooldown): {_dedup_key(alert)}")
        return

    logger.info(f"🚨 ALERT: [{alert['severity']}] {alert['alert_type']} on {alert['service']}: {alert['message']}")

    # Fire all channels concurrently
    await asyncio.gather(
        _send_slack(alert),
        _send_discord(alert),
        _send_email(alert),
        _send_webhook(alert),
        return_exceptions=True,
    )


# ── Auto-alert from anomalies ────────────────────────────────────────────────
async def check_and_alert(metrics: List[Dict], anomalies: List[Dict], cluster_id: str = "default"):
    """Evaluate metrics and anomalies, fire alerts for critical conditions."""
    for anomaly in anomalies:
        svc = anomaly.get("service", "unknown")
        ns = anomaly.get("namespace", "")
        severity = anomaly.get("severity", "warning")
        atypes = anomaly.get("anomaly_types", [])

        if severity == "critical" or anomaly.get("crash_loop") or anomaly.get("oom_killed"):
            alert = create_alert(
                service=svc,
                alert_type=", ".join(atypes) or "Critical Anomaly",
                severity="critical",
                message=_build_alert_message(anomaly),
                namespace=ns,
                cluster_id=cluster_id,
            )
            asyncio.create_task(fire_alert(alert))
        elif severity == "warning" and len(atypes) >= 2:
            alert = create_alert(
                service=svc,
                alert_type=", ".join(atypes[:2]),
                severity="warning",
                message=_build_alert_message(anomaly),
                namespace=ns,
                cluster_id=cluster_id,
            )
            asyncio.create_task(fire_alert(alert))

    # Node-level alerts from metrics
    for m in metrics:
        if m.get("cpu_percent", 0) > 95:
            alert = create_alert(
                service=m["service"],
                alert_type="CPU Critical",
                severity="critical",
                message=f"CPU usage at {m['cpu_percent']}% on {m['service']} ({m['namespace']})",
                namespace=m.get("namespace", ""),
                cluster_id=cluster_id,
            )
            asyncio.create_task(fire_alert(alert))

        if m.get("pvc_usage_percent", 0) > 95:
            alert = create_alert(
                service=m["service"],
                alert_type="PVC Saturation",
                severity="critical",
                message=f"PVC usage at {m['pvc_usage_percent']}% on {m['service']} — immediate expansion required",
                namespace=m.get("namespace", ""),
                cluster_id=cluster_id,
            )
            asyncio.create_task(fire_alert(alert))


def _build_alert_message(anomaly: Dict) -> str:
    svc = anomaly.get("service", "unknown")
    atypes = anomaly.get("anomaly_types", [])
    msg = f"Anomaly detected on {svc}: {', '.join(atypes)}."
    if anomaly.get("crash_loop"):
        msg += " Pod is in CrashLoopBackOff — immediate attention required."
    if anomaly.get("oom_killed"):
        msg += " Pod was OOMKilled — memory limits need increase."
    return msg
