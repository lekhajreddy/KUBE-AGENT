'use client';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, AlertCircle, Shield, Activity } from 'lucide-react';
import { AnomalyData, CorrelationData } from '@/types';

interface Props {
  anomalies: AnomalyData[];
  correlationIntelligence?: CorrelationData;
}

export default function ActiveAnomalies({ anomalies, correlationIntelligence }: Props) {
  const criticalCount = anomalies.filter(a => a.severity === 'critical').length;
  const warningCount = anomalies.filter(a => a.severity === 'warning').length;

  return (
    <div className="glass-card rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Activity className="w-4 h-4 text-amber-400" />
          Active Anomalies
        </h3>
        <div className="flex items-center gap-2">
          {criticalCount > 0 && (
            <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-400 text-[9px] font-bold rounded border border-rose-500/30">
              {criticalCount} critical
            </span>
          )}
          {warningCount > 0 && (
            <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-[9px] font-bold rounded border border-amber-500/30">
              {warningCount} warning
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2 max-h-[320px] overflow-y-auto pr-0.5">
        <AnimatePresence>
          {anomalies.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-6 text-slate-600"
            >
              <Shield className="w-8 h-8 text-emerald-500/30 mb-2" />
              <p className="text-[10px]">No active anomalies</p>
            </motion.div>
          )}

          {anomalies.map((a, i) => {
            const score = a.anomaly_score || 0;
            const confidence = (a.confidence || 0) * 100;
            const isCritical = a.severity === 'critical';

            return (
              <motion.div
                key={`${a.service}-${i}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className={`p-3 rounded-xl border ${
                  isCritical ? 'border-rose-500/30 bg-rose-500/5' : 'border-amber-500/30 bg-amber-500/5'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    {isCritical
                      ? <AlertCircle className="w-3.5 h-3.5 text-rose-400 mt-0.5 flex-shrink-0" />
                      : <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 flex-shrink-0" />
                    }
                    <div>
                      <p className="text-[10px] font-bold text-slate-200">{a.service}</p>
                      <p className="text-[9px] text-slate-500">{a.namespace}</p>
                    </div>
                  </div>
                  <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-full border ${
                    isCritical
                      ? 'text-rose-400 border-rose-500/30 bg-rose-500/10'
                      : 'text-amber-400 border-amber-500/30 bg-amber-500/10'
                  }`}>
                    {a.severity}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap gap-1">
                  {a.anomaly_types.map(t => (
                    <span key={t} className="text-[8px] px-1.5 py-0.5 bg-black/30 rounded font-mono text-slate-300">
                      {t}
                    </span>
                  ))}
                </div>

                <div className="mt-2 flex items-center gap-3 text-[8px] text-slate-600">
                  <span>Score: <span className={isCritical ? 'text-rose-400' : 'text-amber-400'}>{score.toFixed(3)}</span></span>
                  <span>Confidence: <span className="text-slate-400">{confidence.toFixed(0)}%</span></span>
                  <span>Method: <span className="text-slate-400">{a.detection_method}</span></span>
                </div>

                {a.threshold_violations && a.threshold_violations.length > 0 && (
                  <div className="mt-1.5 flex gap-1.5 flex-wrap">
                    {a.threshold_violations.slice(0, 3).map((v, j) => (
                      <span key={j} className="text-[7px] font-mono bg-black/20 px-1 py-0.5 rounded text-slate-500">
                        {v.metric}: {v.value.toFixed(1)}/{v.threshold}
                      </span>
                    ))}
                  </div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {correlationIntelligence?.spike_analysis && correlationIntelligence.spike_analysis.length > 0 && (
        <div className="pt-2 border-t border-slate-800/60">
          <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider mb-1.5">Recent Spikes</p>
          <div className="flex flex-wrap gap-1">
            {correlationIntelligence.spike_analysis.slice(0, 6).map((s, i) => (
              <span key={i} className={`text-[7px] px-1.5 py-0.5 rounded font-mono ${
                s.severity === 'critical' ? 'bg-rose-500/10 text-rose-400' : 'bg-amber-500/10 text-amber-400'
              }`}>
                {s.service}: {s.metric} {s.value}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
