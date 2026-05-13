"""
KubeMind — Network Intelligence Agent
Detects traffic anomalies, service storms, and network-related failures.
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger("kubemind.agent.network")


class NetworkAgent:
    def __init__(self):
        self._rx_history: Dict[str, List[float]] = {}
        self._tx_history: Dict[str, List[float]] = {}

    def analyze(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        insights = []

        for m in metrics:
            svc = m["service"]
            ns = m.get("namespace", "")
            net_in = m.get("network_in_kbps", 0)
            net_out = m.get("network_out_kbps", 0)

            # Track history
            self._rx_history.setdefault(svc, []).append(net_in)
            self._tx_history.setdefault(svc, []).append(net_out)
            if len(self._rx_history[svc]) > 60:
                self._rx_history[svc].pop(0)
            if len(self._tx_history[svc]) > 60:
                self._tx_history[svc].pop(0)

            # ── Traffic Spike Detection ───────────────────────────────────
            rx_hist = self._rx_history.get(svc, [])
            if len(rx_hist) >= 10:
                avg_rx = sum(rx_hist[-10:]) / 10
                if avg_rx > 0 and net_in > avg_rx * 3:
                    insights.append({
                        "agent": "network",
                        "type": "traffic_spike_rx",
                        "severity": "warning",
                        "service": svc,
                        "namespace": ns,
                        "message": f"{svc} receiving 3x normal traffic ({net_in:.0f} vs avg {avg_rx:.0f} kbps). "
                                   f"Possible retry storm or DDoS. Check upstream callers.",
                        "value": net_in,
                        "average": round(avg_rx, 1),
                    })

            tx_hist = self._tx_history.get(svc, [])
            if len(tx_hist) >= 10:
                avg_tx = sum(tx_hist[-10:]) / 10
                if avg_tx > 0 and net_out > avg_tx * 3:
                    insights.append({
                        "agent": "network",
                        "type": "traffic_spike_tx",
                        "severity": "warning",
                        "service": svc,
                        "namespace": ns,
                        "message": f"{svc} sending 3x normal outbound traffic ({net_out:.0f} vs avg {avg_tx:.0f} kbps). "
                                   f"Check for runaway API calls or data sync storms.",
                        "value": net_out,
                        "average": round(avg_tx, 1),
                    })

            # ── Asymmetric traffic (high out, low in = possible data exfiltration) ──
            if net_out > 5000 and net_in < 100:
                insights.append({
                    "agent": "network",
                    "type": "asymmetric_traffic",
                    "severity": "warning",
                    "service": svc,
                    "namespace": ns,
                    "message": f"{svc} has highly asymmetric traffic (out: {net_out:.0f}, in: {net_in:.0f} kbps). "
                               f"Audit outbound connections and apply NetworkPolicy egress rules.",
                    "value_out": net_out,
                    "value_in": net_in,
                })

        # ── Service Storm Detection ───────────────────────────────────────
        # Many services in same namespace with simultaneous traffic spikes
        ns_spikes: Dict[str, List[str]] = defaultdict(list)
        for m in metrics:
            net_in = m.get("network_in_kbps", 0)
            if net_in > 5000:
                ns_spikes[m.get("namespace", "")].append(m["service"])

        for ns, spiking_svcs in ns_spikes.items():
            if len(spiking_svcs) >= 3:
                insights.append({
                    "agent": "network",
                    "type": "service_storm",
                    "severity": "critical",
                    "service": spiking_svcs[0],
                    "namespace": ns,
                    "message": f"Service storm detected in namespace {ns} — {len(spiking_svcs)} services "
                               f"with simultaneous traffic spikes: {', '.join(spiking_svcs[:5])}. "
                               f"Check for cascade retry loops or circuit breaker failures.",
                    "affected_services": spiking_svcs,
                })

        return insights


network_agent = NetworkAgent()
