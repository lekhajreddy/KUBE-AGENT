'use client';
import { motion } from 'framer-motion';
import { Gauge, TrendingUp, TrendingDown } from 'lucide-react';
import { HealthScore, CorrelationData } from '@/types';

interface Props {
  healthScore?: HealthScore;
  correlationIntelligence?: CorrelationData;
}

export default function ClusterHealthCard({ healthScore }: Props) {
  if (!healthScore) {
    return (
      <div className="glass-card rounded-2xl p-4 flex items-center justify-center">
        <p className="text-xs text-slate-600">No health data available</p>
      </div>
    );
  }

  const { score, level, factors } = healthScore;
  const isHealthy = level === 'healthy';
  const isDegraded = level === 'degraded';
  const arcAngle = (score / 100) * 360;
  const color = isHealthy ? '#34d399' : isDegraded ? '#fbbf24' : '#f43f5e';

  return (
    <div className="glass-card rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Gauge className="w-4 h-4 text-sky-400" />
          Cluster Health
        </h3>
      </div>

      <div className="flex items-center gap-4">
        {/* Gauge */}
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="32" fill="none" stroke="#1e293b" strokeWidth="6" />
            <motion.circle
              cx="40" cy="40" r="32" fill="none"
              stroke={color} strokeWidth="6" strokeLinecap="round"
              strokeDasharray={`${(arcAngle / 360) * 201} 201`}
              initial={{ strokeDasharray: '0 201' }}
              animate={{ strokeDasharray: `${(arcAngle / 360) * 201} 201` }}
              transition={{ duration: 1, ease: 'easeOut' }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-bold" style={{ color }}>{score}</span>
          </div>
        </div>

        <div className="flex-1">
          <div className={`text-[10px] font-bold uppercase tracking-wider ${
            isHealthy ? 'text-emerald-400' : isDegraded ? 'text-amber-400' : 'text-rose-400'
          }`}>
            {level}
          </div>
          <div className="flex items-center gap-1 mt-1">
            {score >= 80 ? (
              <TrendingUp className="w-3 h-3 text-emerald-400" />
            ) : (
              <TrendingDown className="w-3 h-3 text-rose-400" />
            )}
            <span className="text-[9px] text-slate-500">
              {isHealthy ? 'All systems nominal' : `${factors.length} degrading factors`}
            </span>
          </div>
        </div>
      </div>

      {factors.filter(f => f.deduction > 0).length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-slate-800/60">
          {factors.filter(f => f.deduction > 0).map((f) => (
            <div key={f.factor} className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  f.deduction > 10 ? 'bg-rose-500' : f.deduction > 5 ? 'bg-amber-500' : 'bg-sky-500'
                }`} />
                <span className="text-[10px] text-slate-400">{f.factor}</span>
                {f.count > 0 && (
                  <span className="text-[8px] text-slate-600">({f.count} pods)</span>
                )}
              </div>
              <span className="text-[10px] font-mono text-slate-600">-{f.deduction}pts</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
