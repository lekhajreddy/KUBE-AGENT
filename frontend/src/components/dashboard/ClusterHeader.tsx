'use client';
import { ClusterSummary } from '@/types';
import { Activity, Globe, Hexagon } from 'lucide-react';
import { motion } from 'framer-motion';

interface Props {
  summary: ClusterSummary | null;
  wsStatus: 'connecting' | 'open' | 'closed';
  lastTs: string;
}

const healthConfig = {
  Healthy:  { color: 'text-emerald-400', dot: 'bg-emerald-500', label: 'Healthy' },
  Degraded: { color: 'text-amber-400',   dot: 'bg-amber-500',  label: 'Degraded' },
  Critical: { color: 'text-rose-400',    dot: 'bg-rose-500',   label: 'Critical' },
  Unknown:  { color: 'text-slate-400',   dot: 'bg-slate-500',  label: 'Unknown' },
};

export default function ClusterHeader({ summary, wsStatus, lastTs }: Props) {
  const health = summary?.cluster_health ?? 'Healthy';
  const cfg = healthConfig[health] ?? healthConfig.Healthy;
  const ts = lastTs ? new Date(lastTs).toLocaleTimeString() : '--:--:--';

  return (
    <div className="flex items-center gap-3 min-w-0">
      {/* Brand */}
      <div className="flex items-center gap-2.5 flex-shrink-0">
        <motion.div
          className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-500/20 to-indigo-600/20 border border-sky-500/20 flex items-center justify-center"
          animate={{ boxShadow: ['0 0 0px rgba(56,189,248,0.2)', '0 0 14px rgba(56,189,248,0.25)', '0 0 0px rgba(56,189,248,0.2)'] }}
          transition={{ duration: 2.5, repeat: Infinity }}
        >
          <Hexagon className="w-4 h-4 text-sky-400" />
        </motion.div>
        <div className="leading-none">
          <h1 className="font-bold text-sm tracking-tight text-gradient-sky">KubeMind AI</h1>
          <p className="text-[8px] text-slate-600 mt-0.5 tracking-wide">Kubernetes Intelligence</p>
        </div>
      </div>

      {/* Divider */}
      <div className="w-px h-8 bg-white/[0.06]" />

      {/* Health Badge */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.03] border border-white/[0.06]">
          <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
          <span className={`text-[10px] font-bold ${cfg.color}`}>
            {cfg.label}
          </span>
        </div>
      </div>

      {/* Namespaces & Pills */}
      <div className="hidden md:flex items-center gap-2 text-[9px] text-slate-600">
        <Globe className="w-3 h-3 text-slate-600" />
        <span className="font-mono">{(summary?.namespaces?.length ?? 0)} ns</span>
        <span className="text-slate-700">·</span>
        <span className="font-mono">{summary?.total_services ?? 0} svc</span>
        {(summary?.degraded_services ?? 0) > 0 && (
          <>
            <span className="text-slate-700">·</span>
            <span className="text-rose-400 font-bold">{summary?.degraded_services} degraded</span>
          </>
        )}
      </div>
    </div>
  );
}
