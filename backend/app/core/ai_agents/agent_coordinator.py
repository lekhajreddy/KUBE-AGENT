"""
KubeMind — AI Agent Coordinator
Orchestrates all specialized AI agents and merges their insights.
"""
import logging
from typing import Any, Dict, List, Optional

from app.core.ai_agents.cpu_agent import cpu_agent
from app.core.ai_agents.memory_agent import memory_agent
from app.core.ai_agents.storage_agent import storage_agent
from app.core.ai_agents.network_agent import network_agent
from app.core.ai_agents.correlation_agent import correlation_agent

logger = logging.getLogger("kubemind.agent.coordinator")

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "normal": 3}


class AgentCoordinator:
    """Runs all AI agents and produces unified insights."""

    def analyze_all(
        self,
        metrics: List[Dict[str, Any]],
        anomalies: List[Dict[str, Any]],
        topology: Optional[Dict[str, Any]] = None,
        pvcs: List[Dict] = None,
    ) -> List[Dict[str, Any]]:
        all_insights = []

        # Run specialized agents
        try:
            all_insights.extend(cpu_agent.analyze(metrics))
        except Exception as e:
            logger.error(f"CPU agent error: {e}")

        try:
            all_insights.extend(memory_agent.analyze(metrics))
        except Exception as e:
            logger.error(f"Memory agent error: {e}")

        try:
            all_insights.extend(storage_agent.analyze(metrics, pvcs))
        except Exception as e:
            logger.error(f"Storage agent error: {e}")

        try:
            all_insights.extend(network_agent.analyze(metrics))
        except Exception as e:
            logger.error(f"Network agent error: {e}")

        # Run correlation agent last (needs insights from other agents)
        try:
            correlation_insights = correlation_agent.analyze(
                metrics, anomalies, topology, all_insights
            )
            all_insights.extend(correlation_insights)
        except Exception as e:
            logger.error(f"Correlation agent error: {e}")

        # Sort by severity
        all_insights.sort(key=lambda i: SEVERITY_ORDER.get(i.get("severity", "normal"), 9))

        # Deduplicate by service+type
        seen = set()
        unique = []
        for insight in all_insights:
            key = f"{insight.get('service', '')}:{insight.get('type', '')}"
            if key not in seen:
                seen.add(key)
                unique.append(insight)

        return unique[:25]  # Cap at 25 insights


agent_coordinator = AgentCoordinator()
