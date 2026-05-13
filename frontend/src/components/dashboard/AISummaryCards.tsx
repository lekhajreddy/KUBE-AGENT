'use client';
import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, AlertTriangle, AlertCircle, CheckCircle, ChevronDown, Lightbulb, TrendingUp, Gauge } from 'lucide-react';
import { ServiceMetrics, AnomalyData, CorrelationData, HealthScore, ExhaustionPrediction } from '@/types';

interface Props {
  metrics: ServiceMetrics[];
  anomalies: AnomalyData[];
  correlationIntelligence?: CorrelationData;
  healthScore?: HealthScore;
  exhaustionPredictions?: ExhaustionPrediction[];
}

function NarrativeCard({
  icon, title, description, severity, actions, confidence,
}: {
  icon: React.ReactNode; title: string; description: string;
  severity: 'critical' | 'warning' | 'info' | 'healthy';
  actions?: string[]; confidence?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const styles = {
    critical: { border: 'border-rose-500/30', bg: 'bg-rose-500/5', text: 'text-rose-400', icon: 'text-rose-400' },
    warning: { border: 'border-amber-500/30', bg: 'bg-amber-500/5', text: 'text-amber-400', icon: 'text-amber-400' },
    info: { border: 'border-sky-500/30', bg: 'bg-sky-500/5', text: 'text-sky-400', icon: 'text-sky-400' },
    healthy: { border: 'border-emerald-500/30', bg: 'bg-emerald-500/5', text: 'text-emerald-400', icon: 'text-emerald-400' },
  };
  const s = styles[severity];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border ${s.border} ${s.bg} overflow-hidden`}
    >
      <button onClick={() => setExpanded(!expanded)} className="w-full p-3 text-left">
        <div className="flex items-start gap-2.5">
          <div className={`mt-0.5 ${s.icon}`}>{icon}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="font-bold text-xs text-slate-200">{title}</span>
              {confidence !== undefined && (
                <span className="text-[8px] font-mono text-slate-500 bg-slate-800 px-1 py-0.5 rounded">
                  {(confidence * 100).toFixed(0)}% confidence
                </span>
              )}
            </div>
            <p className="text-[10px] text-slate-400 leading-relaxed">{description}</p>
          </div>
          <ChevronDown className={`w-3 h-3 text-slate-600 mt-0.5 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>
      <AnimatePresence>
        {expanded && actions && actions.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="px-3 pb-3"
          >
            <div className="border-t border-slate-700/50 pt-2 mt-1">
              <p className="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Recommended Actions</p>
              <div className="space-y-1">
                {actions.map((a, i) => (
                  <div key={i} className="flex items-start gap-1.5 text-[9px] text-slate-400">
                    <Lightbulb className="w-2.5 h-2.5 text-amber-400 mt-0.5 flex-shrink-0" />
                    <span>{a}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function AISummaryCards({ metrics, anomalies, correlationIntelligence, healthScore, exhaustionPredictions }: Props) {
  const narratives = useMemo(() => {
    const cards: Array<{ icon: React.ReactNode; title: string; description: string; severity: 'critical' | 'warning' | 'info' | 'healthy'; actions?: string[]; confidence?: number }> = [];

    // Check for critical anomalies
    const criticalAnomalies = anomalies.filter(a => a.severity === 'critical');
    const warningAnomalies = anomalies.filter(a => a.severity === 'warning');

    if (criticalAnomalies.length > 0) {
      const pods = criticalAnomalies.map(a => a.service).join(', ');
      const types = Array.from(new Set(criticalAnomalies.flatMap(a => a.anomaly_types))).join(', ');
      cards.push({
        icon: <AlertCircle className="w-3.5 h-3.5" />,
        title: `Critical Anomaly Detected in ${criticalAnomalies.length} Pod${criticalAnomalies.length > 1 ? 's' : ''}`,
        description: `KubeMind detected ${types} in ${pods}. Immediate attention required to prevent cascading failures.`,
        severity: 'critical',
        confidence: Math.max(...criticalAnomalies.map(a => a.confidence)),
        actions: criticalAnomalies.flatMap(a => [
          `Run kubectl describe pod ${a.service} -n ${a.namespace || 'default'} to inspect current state`,
          `Check resource limits and increase if needed for ${a.service}`,
          `Review recent logs: kubectl logs ${a.service} -n ${a.namespace || 'default'} --previous`,
        ]).slice(0, 3),
      });
    }

    // Check for impact chains
    if (correlationIntelligence?.impact_chains) {
      for (const chain of correlationIntelligence.impact_chains) {
        if (chain.anomaly_count >= 2) {
          const root = chain.chain.find(c => c.is_anomaly);
          const impacted = chain.chain.filter(c => c.is_anomaly).map(c => c.service);
          const triggers = Array.from(new Set(chain.chain.flatMap(c => c.triggers))).join(', ');
          cards.push({
            icon: <TrendingUp className="w-3.5 h-3.5" />,
            title: `Cascading Impact in ${chain.namespace}`,
            description: `Impact chain detected: ${impacted.join(' → ')}. Triggered by ${triggers}. Total impact score: ${chain.total_impact}.`,
            severity: 'critical',
            actions: [
              `Resolve root cause in ${root?.service || impacted[0]} first`,
              `Scale affected deployments in ${chain.namespace} namespace`,
              `Review service mesh telemetry for request flow`,
            ],
          });
        }
      }
    }

    // Check for metric correlations
    if (correlationIntelligence?.correlations) {
      const strong = correlationIntelligence.correlations.filter(c => c.strength === 'strong');
      for (const corr of strong.slice(0, 2)) {
        cards.push({
          icon: <Gauge className="w-3.5 h-3.5" />,
          title: `Strong Correlation: ${corr.metric_a} ↔ ${corr.metric_b}`,
          description: `${corr.interpretation} in ${corr.service}. Correlation coefficient: ${corr.correlation}. This relationship may indicate a systemic pattern.`,
          severity: 'info',
          confidence: Math.abs(corr.correlation),
          actions: [
            `Monitor ${corr.metric_a} and ${corr.metric_b} together on ${corr.service}`,
            `Set up combined alerting for both metrics`,
          ],
        });
      }
    }

    // Resource exhaustion predictions
    if (exhaustionPredictions) {
      for (const pred of exhaustionPredictions.slice(0, 2)) {
        cards.push({
          icon: <AlertTriangle className="w-3.5 h-3.5" />,
          title: `${pred.metric} Exhaustion Expected in ${pred.eta_human}`,
          description: `${pred.service} will reach critical ${pred.metric} threshold (${pred.threshold}) in approximately ${pred.eta_human}. Current: ${pred.current_value}, trending ${pred.slope > 0 ? 'upward' : 'stable'}.`,
          severity: pred.severity as 'critical' | 'warning' | 'info',
          actions: [
            `Increase ${pred.metric} resource limits for ${pred.service} proactively`,
            `Enable HPA with proactive scaling rules`,
            `Review usage patterns and optimize if possible`,
          ],
        });
      }
    }

    // Health score
    if (healthScore) {
      const topFactors = healthScore.factors.filter(f => f.deduction > 0).sort((a, b) => b.deduction - a.deduction);
      if (healthScore.score < 80 && topFactors.length > 0) {
        cards.push({
          icon: <Gauge className="w-3.5 h-3.5" />,
          title: `Cluster Health Score: ${healthScore.score}/100 (${healthScore.level})`,
          description: `Top factors: ${topFactors.slice(0, 3).map(f => `${f.factor} (-${f.deduction}pts, ${f.count} pods)`).join('; ')}.`,
          severity: healthScore.level === 'critical' ? 'critical' : 'warning',
          actions: topFactors.slice(0, 3).map(f => `Reduce ${f.factor.toLowerCase()} impact: currently affecting ${f.count} pods`),
        });
      } else if (healthScore.score >= 80) {
        cards.push({
          icon: <CheckCircle className="w-3.5 h-3.5" />,
          title: `Cluster Healthy: ${healthScore.score}/100`,
          description: `All major health factors are within acceptable ranges. No systemic issues detected.`,
          severity: 'healthy',
        });
      }
    }

    // General info if no issues
    if (cards.length === 0 && metrics.length > 0) {
      const totalCPU = metrics.reduce((s, m) => s + (m.cpu_percent || 0), 0);
      const avgCPU = (totalCPU / metrics.length).toFixed(1);
      cards.push({
        icon: <Brain className="w-3.5 h-3.5" />,
        title: 'Infrastructure Operating Normally',
        description: `KubeMind is monitoring ${metrics.length} services across ${new Set(metrics.map(m => m.namespace)).size} namespaces. Average CPU: ${avgCPU}%. No anomalies detected.`,
        severity: 'healthy',
      });
    }

    return cards;
  }, [metrics, anomalies, correlationIntelligence, healthScore, exhaustionPredictions]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Brain className="w-4 h-4 text-violet-400" />
          AI Operational Narratives
        </h3>
        <span className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">
          {narratives.length} insight{narratives.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="space-y-2 max-h-[400px] overflow-y-auto pr-0.5">
        <AnimatePresence>
          {narratives.map((card, i) => (
            <NarrativeCard key={i} {...card} />
          ))}
        </AnimatePresence>
      </div>
      <div className="flex items-center gap-1.5 pt-1">
        <span className="w-1 h-1 rounded-full bg-violet-500 animate-pulse" />
        <span className="text-[8px] text-slate-600">AI-powered infrastructure reasoning</span>
      </div>
    </div>
  );
}
