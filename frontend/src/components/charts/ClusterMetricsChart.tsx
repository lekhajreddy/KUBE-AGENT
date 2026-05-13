'use client';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { ServiceMetrics } from '@/types';

interface Props { metrics: ServiceMetrics[] }

const DOMAIN_COLORS: Record<string, string> = {
  'Traffic Infrastructure':   '#38bdf8',
  'Energy Infrastructure':    '#34d399',
  'Campus Infrastructure':    '#a78bfa',
  'Industrial Infrastructure':'#fbbf24',
  'Emergency Systems':        '#f43f5e',
};

export default function ClusterMetricsChart({ metrics }: Props) {
  if (!metrics.length) return null;

  // Aggregate avg cpu per domain
  const byDomain: Record<string, { cpu: number[]; mem: number[] }> = {};
  for (const m of metrics) {
    if (!byDomain[m.domain]) byDomain[m.domain] = { cpu: [], mem: [] };
    byDomain[m.domain].cpu.push(m.cpu_percent);
    byDomain[m.domain].mem.push(m.memory_mb);
  }

  const point: Record<string, number> = {};
  for (const [domain, vals] of Object.entries(byDomain)) {
    point[domain.split(' ')[0]] = Math.round(vals.cpu.reduce((a, b) => a + b, 0) / vals.cpu.length * 10) / 10;
  }

  return (
    <div className="h-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={[point]} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            {Object.entries(DOMAIN_COLORS).map(([d, c]) => (
              <linearGradient key={d} id={`grad-${d.split(' ')[0]}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={c} stopOpacity={0.3} />
                <stop offset="95%" stopColor={c} stopOpacity={0}   />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 11 }} />
          <YAxis tick={{ fill: '#475569', fontSize: 11 }} domain={[0, 100]} />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#94a3b8' }}
            itemStyle={{ color: '#f1f5f9' }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
          {Object.entries(DOMAIN_COLORS).map(([d, c]) => (
            <Area
              key={d}
              type="monotone"
              dataKey={d.split(' ')[0]}
              stroke={c}
              strokeWidth={2}
              fill={`url(#grad-${d.split(' ')[0]})`}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
