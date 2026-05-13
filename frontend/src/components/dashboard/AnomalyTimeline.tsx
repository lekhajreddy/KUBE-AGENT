'use client';
import { AnomalyData, RCAResult } from '@/types';
import { ShieldAlert, GitBranch, Clock, AlertOctagon } from 'lucide-react';
import { motion } from 'framer-motion';

interface Props { anomalies: AnomalyData[]; rca: RCAResult[] }

const SEV_STYLE: Record<string, string> = {
  critical: 'border-rose-500/30 bg-rose-500/5 text-rose-400',
  warning:  'border-amber-500/30 bg-amber-500/5 text-amber-400',
  normal:   'border-emerald-500/30 bg-emerald-500/5 text-emerald-400',
};

export default function AnomalyTimeline({ anomalies, rca }: Props) {
  const rcaMap = new Map(rca.map(r => [r.service, r]));

  if (!anomalies.length) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 text-slate-600">
        <ShieldAlert className="w-12 h-12 opacity-30" />
        <p className="text-sm">No anomalies detected</p>
        <p className="text-xs opacity-60">All services operating within thresholds</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto px-4 py-3 space-y-3">
      {anomalies.map((a, i) => {
        const rcaInfo = rcaMap.get(a.service);
        const sev = a.severity;
        return (
          <motion.div key={`${a.service}-${i}`}
            initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`p-3 rounded-xl border ${SEV_STYLE[sev] ?? SEV_STYLE.warning}`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-3.5 h-3.5 flex-shrink-0" />
                <span className="font-bold text-sm">{a.service}</span>
                <span className="text-[9px] text-slate-500">{a.namespace}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border" style={{ borderColor: 'inherit' }}>
                  {sev}
                </span>
                <span className="text-[9px] text-slate-500 flex items-center gap-1">
                  <Clock className="w-2.5 h-2.5" />
                  {new Date(a.timestamp).toLocaleTimeString()}
                </span>
              </div>
            </div>
            <div className="flex flex-wrap gap-1 mb-2">
              {a.anomaly_types.map(t => (
                <span key={t} className="text-[9px] px-1.5 py-0.5 bg-black/20 rounded font-mono">{t}</span>
              ))}
            </div>
            <div className="text-[10px] text-slate-400 space-y-0.5">
              <div>Method: <span className="text-slate-300">{a.detection_method}</span> · Confidence: <span className="text-slate-300">{(a.confidence * 100).toFixed(0)}%</span></div>
              {rcaInfo && (
                <div className="flex items-start gap-1 mt-1.5 pt-1.5 border-t border-white/5">
                  <GitBranch className="w-3 h-3 mt-0.5 text-sky-400 flex-shrink-0" />
                  <span className="text-sky-300/80">{rcaInfo.reasoning}</span>
                </div>
              )}
            </div>
            {a.threshold_violations.length > 0 && (
              <div className="mt-2 grid grid-cols-2 gap-1">
                {a.threshold_violations.slice(0, 4).map((v, j) => (
                  <div key={j} className="text-[9px] bg-black/20 rounded px-1.5 py-1 font-mono">
                    {v.metric}: <span className="font-bold">{typeof v.value === 'number' ? v.value.toFixed(1) : v.value}</span>
                    <span className="text-slate-600"> / {v.threshold}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
