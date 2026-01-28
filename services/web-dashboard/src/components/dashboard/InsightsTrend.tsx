import { Card } from '@/components/ui';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface InsightsTrendProps {
  data: Array<{
    date: string;
    risks: number;
    opportunities: number;
    total: number;
  }>;
}

export function InsightsTrend({ data }: InsightsTrendProps) {
  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Insights Trend</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => {
                const date = new Date(value);
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '0.5rem',
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="risks"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
              name="Risks"
            />
            <Line
              type="monotone"
              dataKey="opportunities"
              stroke="#22c55e"
              strokeWidth={2}
              dot={false}
              name="Opportunities"
            />
            <Line
              type="monotone"
              dataKey="total"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={false}
              name="Total"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
