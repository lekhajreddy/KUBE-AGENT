'use client';
import { Recommendation } from '@/types';
import { Lightbulb, ChevronRight } from 'lucide-react';

const PRIORITY_STYLE: Record<string, string> = {
  Critical: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  High:     'text-amber-400 bg-amber-500/10 border-amber-500/20',
  Medium:   'text-sky-400 bg-sky-500/10 border-sky-500/20',
  Low:      'text-slate-400 bg-slate-500/10 border-slate-500/20',
};

export default function RecommendationsPanel({ recs }: { recs: Recommendation[] }) {
  if (!recs.length) {
    return (
      <div className="text-center py-6 text-slate-600 text-xs">
        No recommendations at this time
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {recs.slice(0, 6).map(r => (
        <div key={r.id} className="p-3 bg-slate-950/60 border border-slate-800/60 rounded-xl">
          <div className="flex items-start justify-between gap-2 mb-1">
            <div className="flex items-center gap-1.5">
              <Lightbulb className="w-3 h-3 text-amber-400 flex-shrink-0" />
              <span className="text-[10px] font-bold text-slate-200">{r.service}</span>
            </div>
            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${PRIORITY_STYLE[r.priority] ?? PRIORITY_STYLE.Medium}`}>
              {r.priority}
            </span>
          </div>
          <p className="text-[10px] text-sky-400 font-medium mb-0.5">{r.type}</p>
          <p className="text-[10px] text-slate-400 leading-relaxed">{r.action}</p>
          <p className="text-[9px] text-slate-600 mt-1 italic">{r.reason}</p>
        </div>
      ))}
    </div>
  );
}
