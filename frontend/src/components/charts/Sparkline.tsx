'use client';
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts';

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
}

export function Sparkline({ data, color = '#38bdf8', height = 36 }: SparklineProps) {
  const chartData = data.map((v, i) => ({ v, i }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          content={({ active, payload }) =>
            active && payload?.length ? (
              <div className="glass-card text-xs px-2 py-1 rounded">{Number(payload[0].value).toFixed(1)}</div>
            ) : null
          }
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
