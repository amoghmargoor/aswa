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
