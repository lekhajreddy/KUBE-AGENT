'use client';
import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { GitBranch, ArrowUp, ArrowDown, Minus, TrendingUp, Activity } from 'lucide-react';
import { CorrelationData } from '@/types';

interface Props {
  correlationIntelligence?: CorrelationData;
}

function CorrelationBar({ value, label }: { value: number; label: string }) {
  const abs = Math.abs(value);
  const width = Math.min(Math.abs(value) * 100, 100);
  const isPositive = value >= 0;
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[8px] text-slate-500 w-16 text-right">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden relative">
        <div
          className={`h-full rounded-full ${isPositive ? 'bg-emerald-500/60' : 'bg-rose-500/60'}`}
          style={{ width: `${width}%`, marginLeft: isPositive ? '50%' : `${50 - width}%` }}
        />
      </div>
      <span className="text-[8px] font-mono text-slate-400 w-8">{value.toFixed(2)}</span>
    </div>
  );
}

export default function CorrelationInsights({ correlationIntelligence }: Props) {
  const correlations = useMemo(() => {
    if (!correlationIntelligence?.correlations) return [];
    return correlationIntelligence.correlations;
  }, [correlationIntelligence]);

  const impactChains = useMemo(() => {
    if (!correlationIntelligence?.impact_chains) return [];
    return correlationIntelligence.impact_chains;
  }, [correlationIntelligence]);

  if (!correlationIntelligence) {
    return (
      <div className="glass-card rounded-2xl p-4 flex items-center justify-center">
        <p className="text-xs text-slate-600">No correlation data available</p>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-violet-400" />
          Correlation Intelligence
        </h3>
        <span className="text-[9px] text-slate-500 font-mono">
          {correlations.length} correlations
        </span>
      </div>

      {/* Impact Chains */}
      {impactChains.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">Impact Chains</p>
          {impactChains.slice(0, 3).map((chain, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="p-2 rounded-lg bg-slate-950/60 border border-slate-800/60"
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[9px] font-bold text-sky-400">{chain.namespace}</span>
                <span className="text-[7px] text-slate-600">{chain.anomaly_count} anomalies</span>
              </div>
              <div className="flex items-center gap-1 flex-wrap">
                {chain.chain.map((item, j) => (
                  <span key={j} className="flex items-center gap-0.5">
                    <span className={`text-[8px] px-1 py-0.5 rounded ${
                      item.is_anomaly ? 'bg-rose-500/15 text-rose-400 font-bold' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {item.service.substring(0, 10)}
                    </span>
                    {j < chain.chain.length - 1 && (
                      <TrendingUp className="w-2.5 h-2.5 text-slate-600" />
                    )}
                  </span>
                ))}
              </div>
              <div className="flex gap-1 mt-1">
                {Array.from(new Set(chain.chain.flatMap(c => c.triggers))).slice(0, 3).map((t, j) => (
                  <span key={j} className="text-[7px] px-1 py-0.5 bg-slate-800 rounded text-slate-500 font-mono">{t}</span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Metric Correlations */}
      {correlations.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">Metric Relationships</p>
          <div className="space-y-1 max-h-[200px] overflow-y-auto pr-0.5">
            {correlations.slice(0, 8).map((c, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.03 }}
                className="p-1.5 rounded-lg bg-slate-950/40"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    <span className="text-[8px] font-bold text-slate-300">{c.service}</span>
                    <span className="text-[7px] text-slate-600">({c.metric_a} ↔ {c.metric_b})</span>
                  </div>
                  <span className={`text-[7px] font-bold px-1 rounded ${
                    c.strength === 'strong' ? 'text-emerald-400 bg-emerald-500/10' :
                    c.strength === 'moderate' ? 'text-amber-400 bg-amber-500/10' :
                    'text-slate-500 bg-slate-800'
                  }`}>
                    {c.strength}
                  </span>
                </div>
                <p className="text-[7px] text-slate-600 mt-0.5">{c.interpretation}</p>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {correlations.length === 0 && impactChains.length === 0 && (
        <div className="flex flex-col items-center justify-center py-6 text-slate-600">
          <Activity className="w-6 h-6 opacity-30 mb-2" />
          <p className="text-[10px]">No correlations detected</p>
          <p className="text-[8px] text-slate-700 mt-0.5">Collecting more data for analysis</p>
        </div>
      )}
    </div>
  );
}
