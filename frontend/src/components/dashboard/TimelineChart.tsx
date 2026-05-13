'use client';
import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Activity, Cpu, Database, Wifi, RefreshCw, AlertTriangle, Zap } from 'lucide-react';
import { ServiceMetrics, AnomalyData, ExhaustionPrediction, CorrelationData } from '@/types';

interface TimelineEvent {
  id: string;
  ts: Date;
  type: 'cpu_spike' | 'memory_surge' | 'network_burst' | 'pvc_overload' | 'pod_restart' | 'anomaly_alert' | 'ai_insight';
  service: string;
  value?: number;
  severity?: string;
  label: string;
}

interface Props {
  metrics: ServiceMetrics[];
  anomalies: AnomalyData[];
  exhaustionPredictions?: ExhaustionPrediction[];
  correlationIntelligence?: CorrelationData;
}

const EVENT_CONFIG = {
  cpu_spike: { icon: Cpu, color: '#f43f5e', bg: 'bg-rose-500/15', label: 'CPU Spike' },
  memory_surge: { icon: Database, color: '#a78bfa', bg: 'bg-violet-500/15', label: 'Memory Surge' },
  network_burst: { icon: Wifi, color: '#38bdf8', bg: 'bg-sky-500/15', label: 'Network Burst' },
  pvc_overload: { icon: Activity, color: '#34d399', bg: 'bg-emerald-500/15', label: 'PVC Overload' },
  pod_restart: { icon: RefreshCw, color: '#fbbf24', bg: 'bg-amber-500/15', label: 'Pod Restart' },
  anomaly_alert: { icon: AlertTriangle, color: '#f43f5e', bg: 'bg-rose-500/20', label: 'Anomaly Alert' },
  ai_insight: { icon: Zap, color: '#38bdf8', bg: 'bg-sky-500/10', label: 'AI Insight' },
};

function TimelineDot({ type, isFirst, isLast }: { type: string; isFirst?: boolean; isLast?: boolean }) {
  const cfg = EVENT_CONFIG[type as keyof typeof EVENT_CONFIG] || EVENT_CONFIG.anomaly_alert;
  return (
    <div className="flex flex-col items-center">
      <div className={`w-6 h-6 rounded-full ${cfg.bg} flex items-center justify-center border`} style={{ borderColor: cfg.color }}>
        <cfg.icon className="w-3 h-3" style={{ color: cfg.color }} />
      </div>
      {!isLast && <div className="w-0.5 h-8 bg-slate-800 mt-0.5" />}
    </div>
  );
}

export default function TimelineChart({ metrics, anomalies, exhaustionPredictions, correlationIntelligence }: Props) {
  const events = useMemo(() => {
    const evts: TimelineEvent[] = [];
    const now = new Date();
    let id = 0;

    // Generate events from metrics with high values
    for (const m of metrics) {
      const ts = new Date(now.getTime() - Math.random() * 300000);
      if ((m.cpu_percent || 0) >= 80) {
        evts.push({ id: `cpu-${id++}`, ts, type: 'cpu_spike', service: m.service, value: m.cpu_percent, severity: m.cpu_percent >= 90 ? 'critical' : 'warning', label: `${m.service}: ${m.cpu_percent}% CPU` });
      }
      if ((m.memory_mb || 0) >= 700) {
        evts.push({ id: `mem-${id++}`, ts, type: 'memory_surge', service: m.service, value: m.memory_mb, severity: m.memory_mb >= 1000 ? 'critical' : 'warning', label: `${m.service}: ${m.memory_mb}MB` });
      }
      if ((m.network_in_kbps || 0) >= 5000) {
        evts.push({ id: `net-${id++}`, ts, type: 'network_burst', service: m.service, value: m.network_in_kbps, severity: m.network_in_kbps >= 10000 ? 'critical' : 'warning', label: `${m.service}: ${m.network_in_kbps} kbps` });
      }
      const pvcPct = m.pvc_usage_percent ?? 0;
      if (pvcPct >= 75) {
        evts.push({ id: `pvc-${id++}`, ts, type: 'pvc_overload', service: m.service, value: pvcPct, severity: pvcPct >= 90 ? 'critical' : 'warning', label: `${m.service}: ${pvcPct}%` });
      }
      if ((m.restart_count || 0) >= 3) {
        evts.push({ id: `rst-${id++}`, ts: new Date(now.getTime() - Math.random() * 120000), type: 'pod_restart', service: m.service, value: m.restart_count, label: `${m.service}: ${m.restart_count} restarts` });
      }
    }

    // Add anomaly events
    for (const a of anomalies) {
      const ts = new Date(a.timestamp || now.getTime());
      evts.push({ id: `anomaly-${id++}`, ts, type: 'anomaly_alert', service: a.service, severity: a.severity, label: `${a.service}: ${a.anomaly_types.join(', ')}` });
    }

    // Add exhaustion predictions
    if (exhaustionPredictions) {
      for (const p of exhaustionPredictions.slice(0, 3)) {
        const ts = new Date(now.getTime() + p.eta_minutes * 60000);
        evts.push({ id: `exhaust-${id++}`, ts, type: 'ai_insight', service: p.service, label: `${p.service}: ${p.metric} exhaustion in ${p.eta_human}` });
      }
    }

    // Sort by timestamp
    evts.sort((a, b) => a.ts.getTime() - b.ts.getTime());
    return evts.slice(-20);
  }, [metrics, anomalies, exhaustionPredictions]);

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-slate-600">
        <Activity className="w-8 h-8 opacity-30 mb-2" />
        <p className="text-xs">No timeline events</p>
      </div>
    );
  }

  const startTime = events[0]?.ts || new Date();
  const endTime = events[events.length - 1]?.ts || new Date();
  const range = endTime.getTime() - startTime.getTime() || 1;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Activity className="w-4 h-4 text-sky-400" />
          Operational Timeline
        </h3>
        <span className="text-[9px] text-slate-500 font-mono">
          {events.length} events
        </span>
      </div>

      <div className="relative overflow-x-auto">
        <div className="flex gap-0 min-w-[500px]">
          {events.map((evt, i) => {
            const cfg = EVENT_CONFIG[evt.type];
            const pos = ((evt.ts.getTime() - startTime.getTime()) / range) * 100;
            return (
              <motion.div
                key={evt.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="flex flex-col items-center min-w-[60px]"
                style={{ marginLeft: i === 0 ? 0 : undefined }}
              >
                <div className="flex flex-col items-center">
                  <TimelineDot type={evt.type} isLast={i === events.length - 1} />
                  <div
                    className={`mt-1 px-1.5 py-0.5 rounded text-[8px] font-bold text-center max-w-[60px] leading-tight ${
                      evt.severity === 'critical' ? 'text-rose-400 bg-rose-500/10' :
                      evt.severity === 'warning' ? 'text-amber-400 bg-amber-500/10' :
                      'text-slate-400 bg-slate-800/50'
                    }`}
                  >
                    {cfg.label}
                  </div>
                </div>
                <div className="mt-1 text-[7px] font-mono text-slate-600 text-center leading-tight">
                  {evt.service.length > 12 ? evt.service.substring(0, 10) + '..' : evt.service}
                </div>
                <div className="text-[7px] text-slate-700 font-mono">
                  {evt.ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-3 text-[8px] text-slate-600">
        {Object.entries(EVENT_CONFIG).map(([key, cfg]) => (
          <div key={key} className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.color }} />
            <span>{cfg.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
