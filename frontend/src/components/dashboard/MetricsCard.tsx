import React from 'react';

interface MetricsCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  trend: string;
  color: 'sky' | 'emerald' | 'rose' | 'indigo' | 'amber';
}

const colorMap = {
  sky: 'border-sky-500/20 bg-sky-500/5 text-sky-400',
  emerald: 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400',
  rose: 'border-rose-500/20 bg-rose-500/5 text-rose-400',
  indigo: 'border-indigo-500/20 bg-indigo-500/5 text-indigo-400',
  amber: 'border-amber-500/20 bg-amber-500/5 text-amber-400',
};

export default function MetricsCard({ title, value, icon, trend, color }: MetricsCardProps) {
  return (
    <div className={`p-5 rounded-2xl border ${colorMap[color]} shadow-lg shadow-black/10`}>
      <div className="flex items-center justify-between mb-4">
        <div className="p-2 bg-black/20 rounded-lg">
          {icon}
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider opacity-60">{trend}</span>
      </div>
      <div>
        <p className="text-sm font-medium text-slate-400 mb-1">{title}</p>
        <p className="text-2xl font-bold text-slate-100 tracking-tight">{value}</p>
      </div>
    </div>
  );
}
