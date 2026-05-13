'use client';
import { NLPInsight } from '@/types';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, AlertTriangle, AlertCircle, CheckCircle, Info, Zap } from 'lucide-react';

interface Props {
  insights: NLPInsight[];
}

const SEVERITY_CONFIG = {
  critical: {
    icon:    AlertCircle,
    border:  'border-rose-500/30',
    bg:      'bg-rose-500/8',
    text:    'text-rose-300',
    badge:   'bg-rose-500/20 text-rose-300 border-rose-500/30',
    dot:     'bg-rose-500',
    label:   'CRITICAL',
  },
  warning: {
    icon:    AlertTriangle,
    border:  'border-amber-500/30',
    bg:      'bg-amber-500/8',
    text:    'text-amber-300',
    badge:   'bg-amber-500/20 text-amber-300 border-amber-500/30',
    dot:     'bg-amber-500',
    label:   'WARNING',
  },
  normal: {
    icon:    CheckCircle,
    border:  'border-emerald-500/20',
    bg:      'bg-emerald-500/5',
    text:    'text-emerald-300',
    badge:   'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    dot:     'bg-emerald-500',
    label:   'OK',
  },
  info: {
    icon:    Info,
    border:  'border-sky-500/20',
    bg:      'bg-sky-500/5',
    text:    'text-sky-300',
    badge:   'bg-sky-500/20 text-sky-300 border-sky-500/30',
    dot:     'bg-sky-400',
    label:   'INFO',
  },
};

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return ts;
  }
}

export default function NLPInsightsPanel({ insights }: Props) {
  return (
    <div className="glass-card rounded-2xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Brain className="w-4 h-4 text-violet-400" />
          AI Operational Insights
        </h3>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
          <span className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">
            {insights.length} insights
          </span>
        </div>
      </div>

      {/* Insight list */}
      <div className="space-y-2 max-h-[280px] overflow-y-auto pr-0.5">
        <AnimatePresence initial={false}>
          {insights.length === 0 && (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-8 text-center"
            >
              <CheckCircle className="w-6 h-6 text-emerald-500/40 mb-2" />
              <p className="text-[10px] text-slate-600">No active insights</p>
              <p className="text-[9px] text-slate-700 mt-0.5">Cluster is operating normally</p>
            </motion.div>
          )}

          {insights.map((insight, idx) => {
            const sev = (insight.severity in SEVERITY_CONFIG)
              ? insight.severity as keyof typeof SEVERITY_CONFIG
              : 'info';
            const cfg = SEVERITY_CONFIG[sev];
            const Icon = cfg.icon;

            return (
              <motion.div
                key={insight.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }}
                transition={{ delay: idx * 0.04 }}
                className={`rounded-xl p-3 border ${cfg.border} ${cfg.bg} group`}
              >
                {/* Top row */}
                <div className="flex items-start gap-2">
                  <Icon className={`w-3 h-3 mt-0.5 flex-shrink-0 ${cfg.text}`} />
                  <p className="text-[10px] text-slate-200 leading-relaxed flex-1">
                    {insight.message}
                  </p>
                </div>

                {/* Bottom row */}
                <div className="flex items-center justify-between mt-2 pl-5">
                  <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded border ${cfg.badge}`}>
                    {cfg.label}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-[8px] text-slate-600 font-mono">{formatTs(insight.ts)}</span>
                    <span className="text-[8px] text-slate-700 uppercase tracking-wide">{insight.source}</span>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Powered by */}
      <div className="flex items-center gap-1.5 pt-1 border-t border-slate-800/60">
        <Zap className="w-2.5 h-2.5 text-violet-500" />
        <span className="text-[8px] text-slate-600">
          Powered by AI Correlation Engine + RCA Analysis
        </span>
      </div>
    </div>
  );
}
