# Task 5.3.4: Web Dashboard - Analytics Dashboard

## Context

You are working on the ASWA web dashboard at `/services/web-dashboard/`. Query interface is complete (Task 5.3.3). Now we need to implement analytics dashboards.

## Objective

Create analytics dashboards that:
1. Display key metrics and KPIs
2. Visualize insights trends
3. Show document processing stats
4. Provide user activity analytics
5. Support date range filtering

## Requirements

### 1. Create `/services/web-dashboard/src/pages/Dashboard.tsx`
```typescript
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui';
import { StatsCards } from '@/components/dashboard/StatsCards';
import { InsightsTrend } from '@/components/dashboard/InsightsTrend';
import { TopInsights } from '@/components/dashboard/TopInsights';
import { RecentActivity } from '@/components/dashboard/RecentActivity';
import { DocumentsChart } from '@/components/dashboard/DocumentsChart';
import { DateRangePicker } from '@/components/dashboard/DateRangePicker';
import { api } from '@/services/api';
import { LoadingSpinner } from '@/components/common';
import { subDays, format } from 'date-fns';

export default function Dashboard() {
  const [dateRange, setDateRange] = useState({
    start: subDays(new Date(), 30),
    end: new Date(),
  });

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboardStats', dateRange],
    queryFn: () => api.getDashboardStats({
      startDate: format(dateRange.start, 'yyyy-MM-dd'),
      endDate: format(dateRange.end, 'yyyy-MM-dd'),
    }),
  });

  const { data: insights } = useQuery({
    queryKey: ['topInsights'],
    queryFn: () => api.getInsights({ limit: 5 }),
  });

  const { data: documents } = useQuery({
    queryKey: ['recentDocuments'],
    queryFn: () => api.getDocuments({ limit: 5 }),
  });

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500">Overview of your document intelligence</p>
        </div>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      <StatsCards stats={stats} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <InsightsTrend data={stats?.insightsTrend || []} />
        <DocumentsChart data={stats?.documentsChart || []} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TopInsights insights={insights?.items || []} />
        <RecentActivity documents={documents?.items || []} />
      </div>
    </div>
  );
}
```

### 2. Create `/services/web-dashboard/src/components/dashboard/StatsCards.tsx`
```typescript
import { Card } from '@/components/ui';
import { FileText, Lightbulb, AlertTriangle, TrendingUp, ArrowUp, ArrowDown } from 'lucide-react';

interface StatsCardsProps {
  stats?: {
    totalDocuments: number;
    totalInsights: number;
    totalRisks: number;
    totalOpportunities: number;
    documentsChange: number;
    insightsChange: number;
    risksChange: number;
    opportunitiesChange: number;
  };
}

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: 'Total Documents',
      value: stats?.totalDocuments || 0,
      change: stats?.documentsChange || 0,
      icon: FileText,
      color: 'blue',
    },
    {
      title: 'Total Insights',
      value: stats?.totalInsights || 0,
      change: stats?.insightsChange || 0,
      icon: Lightbulb,
      color: 'purple',
    },
    {
      title: 'Risks Identified',
      value: stats?.totalRisks || 0,
      change: stats?.risksChange || 0,
      icon: AlertTriangle,
      color: 'red',
    },
    {
      title: 'Opportunities',
      value: stats?.totalOpportunities || 0,
      change: stats?.opportunitiesChange || 0,
      icon: TrendingUp,
      color: 'green',
    },
  ];

  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    purple: 'bg-purple-50 text-purple-600',
    red: 'bg-red-50 text-red-600',
    green: 'bg-green-50 text-green-600',
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.title} className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">{card.title}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {card.value.toLocaleString()}
              </p>
              <div className="flex items-center mt-2">
                {card.change > 0 ? (
                  <ArrowUp className="h-4 w-4 text-green-600" />
                ) : card.change < 0 ? (
                  <ArrowDown className="h-4 w-4 text-red-600" />
                ) : null}
                <span
                  className={`text-sm ml-1 ${
                    card.change > 0 ? 'text-green-600' : card.change < 0 ? 'text-red-600' : 'text-gray-500'
                  }`}
                >
                  {Math.abs(card.change)}% vs last period
                </span>
              </div>
            </div>
            <div className={`p-3 rounded-full ${colorClasses[card.color as keyof typeof colorClasses]}`}>
              <card.icon className="h-6 w-6" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
```

### 3. Create `/services/web-dashboard/src/components/dashboard/InsightsTrend.tsx`
```typescript
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
```

### 4. Create `/services/web-dashboard/src/components/dashboard/DocumentsChart.tsx`
```typescript
import { Card } from '@/components/ui';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface DocumentsChartProps {
  data: Array<{
    name: string;
    count: number;
  }>;
}

const COLORS = ['#0ea5e9', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444'];

export function DocumentsChart({ data }: DocumentsChartProps) {
  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Documents by Type</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical">
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 12 }}
              width={100}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '0.5rem',
              }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {data.map((_, index) => (
                <Cell key={index} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
```

### 5. Create `/services/web-dashboard/src/components/dashboard/TopInsights.tsx`
```typescript
import { Card } from '@/components/ui';
import type { Insight } from '@/types';
import { AlertTriangle, TrendingUp, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface TopInsightsProps {
  insights: Insight[];
}

export function TopInsights({ insights }: TopInsightsProps) {
  const severityColors = {
    critical: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-green-100 text-green-700',
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Top Insights</h3>
        <Link
          to="/insights"
          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          View all <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
      <div className="space-y-3">
        {insights.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No insights yet</p>
        ) : (
          insights.map((insight) => (
            <div
              key={insight.id}
              className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div
                className={`p-2 rounded-lg ${
                  insight.type === 'risk' ? 'bg-red-50' : 'bg-green-50'
                }`}
              >
                {insight.type === 'risk' ? (
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                ) : (
                  <TrendingUp className="h-4 w-4 text-green-600" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {insight.title}
                </p>
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                  {insight.description}
                </p>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    severityColors[insight.severity || 'low']
                  }`}>
                    {insight.severity || 'low'}
                  </span>
                  <span className="text-xs text-gray-400">
                    {(insight.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
```

### 6. Create `/services/web-dashboard/src/components/dashboard/RecentActivity.tsx`
```typescript
import { Card } from '@/components/ui';
import type { Document } from '@/types';
import { FileText, CheckCircle, XCircle, Clock, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';

interface RecentActivityProps {
  documents: Document[];
}

export function RecentActivity({ documents }: RecentActivityProps) {
  const statusIcons = {
    completed: <CheckCircle className="h-4 w-4 text-green-600" />,
    failed: <XCircle className="h-4 w-4 text-red-600" />,
    processing: <Clock className="h-4 w-4 text-yellow-600 animate-pulse" />,
    pending: <Clock className="h-4 w-4 text-gray-400" />,
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Recent Documents</h3>
        <Link
          to="/documents"
          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          View all <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
      <div className="space-y-3">
        {documents.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No documents yet</p>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="p-2 bg-gray-100 rounded-lg">
                <FileText className="h-4 w-4 text-gray-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {doc.name}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {statusIcons[doc.status]}
                  <span className="text-xs text-gray-500 capitalize">
                    {doc.status}
                  </span>
                  <span className="text-xs text-gray-300">•</span>
                  <span className="text-xs text-gray-500">
                    {formatDistanceToNow(new Date(doc.uploadedAt), { addSuffix: true })}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">
                  {doc.insightCount}
                </p>
                <p className="text-xs text-gray-500">insights</p>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
```

### 7. Create `/services/web-dashboard/src/components/dashboard/DateRangePicker.tsx`
```typescript
import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui';
import { Calendar, ChevronDown } from 'lucide-react';
import { format, subDays, subMonths, startOfMonth, endOfMonth } from 'date-fns';

interface DateRange {
  start: Date;
  end: Date;
}

interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

const presets = [
  { label: 'Last 7 days', getValue: () => ({ start: subDays(new Date(), 7), end: new Date() }) },
  { label: 'Last 30 days', getValue: () => ({ start: subDays(new Date(), 30), end: new Date() }) },
  { label: 'Last 90 days', getValue: () => ({ start: subDays(new Date(), 90), end: new Date() }) },
  { label: 'This month', getValue: () => ({ start: startOfMonth(new Date()), end: new Date() }) },
  { label: 'Last month', getValue: () => {
    const lastMonth = subMonths(new Date(), 1);
    return { start: startOfMonth(lastMonth), end: endOfMonth(lastMonth) };
  }},
];

export function DateRangePicker({ value, onChange }: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const formatRange = () => {
    return `${format(value.start, 'MMM d, yyyy')} - ${format(value.end, 'MMM d, yyyy')}`;
  };

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="outline"
        onClick={() => setIsOpen(!isOpen)}
        className="min-w-[260px] justify-between"
      >
        <span className="flex items-center gap-2">
          <Calendar className="h-4 w-4" />
          {formatRange()}
        </span>
        <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </Button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
          <div className="p-2">
            {presets.map((preset) => (
              <button
                key={preset.label}
                onClick={() => {
                  onChange(preset.getValue());
                  setIsOpen(false);
                }}
                className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

### 8. Create `/services/web-dashboard/src/components/dashboard/index.ts`
```typescript
export { StatsCards } from './StatsCards';
export { InsightsTrend } from './InsightsTrend';
export { DocumentsChart } from './DocumentsChart';
export { TopInsights } from './TopInsights';
export { RecentActivity } from './RecentActivity';
export { DateRangePicker } from './DateRangePicker';
```

### 9. Update `/services/web-dashboard/src/services/api.ts` - Add dashboard methods
```typescript
// Add to the ApiService class:

async getDashboardStats(params: {
  startDate: string;
  endDate: string;
}): Promise<{
  totalDocuments: number;
  totalInsights: number;
  totalRisks: number;
  totalOpportunities: number;
  documentsChange: number;
  insightsChange: number;
  risksChange: number;
  opportunitiesChange: number;
  insightsTrend: Array<{ date: string; risks: number; opportunities: number; total: number }>;
  documentsChart: Array<{ name: string; count: number }>;
}> {
  const { data } = await this.client.get('/analytics/dashboard', { params });
  return data;
}
```

## Test Requirements

### Create `/services/web-dashboard/src/components/dashboard/StatsCards.test.tsx`
```typescript
import { render, screen } from '@testing-library/react';
import { StatsCards } from './StatsCards';

describe('StatsCards', () => {
  it('renders all stat cards', () => {
    const stats = {
      totalDocuments: 100,
      totalInsights: 250,
      totalRisks: 50,
      totalOpportunities: 75,
      documentsChange: 10,
      insightsChange: 25,
      risksChange: -5,
      opportunitiesChange: 15,
    };

    render(<StatsCards stats={stats} />);

    expect(screen.getByText('Total Documents')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('Total Insights')).toBeInTheDocument();
    expect(screen.getByText('250')).toBeInTheDocument();
  });

  it('shows positive change with green color', () => {
    const stats = {
      totalDocuments: 100,
      totalInsights: 250,
      totalRisks: 50,
      totalOpportunities: 75,
      documentsChange: 10,
      insightsChange: 25,
      risksChange: -5,
      opportunitiesChange: 15,
    };

    render(<StatsCards stats={stats} />);

    const positiveChange = screen.getByText('10% vs last period');
    expect(positiveChange).toHaveClass('text-green-600');
  });
});
```

## Verification

1. Run tests: `npm test`
2. Check dashboard page: Navigate to `/`
3. Verify charts render correctly
4. Test date range filtering
5. Check responsive layout
