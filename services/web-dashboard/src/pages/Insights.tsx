import { useState } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useInsights } from '@/hooks';
import { LoadingSpinner } from '@/components/common';

type InsightFilter = 'all' | 'risk' | 'opportunity' | 'trend' | 'entity';

export default function Insights() {
  const [filter, setFilter] = useState<InsightFilter>('all');

  const { data, isLoading, error } = useInsights({
    type: filter === 'all' ? undefined : filter,
    limit: 20,
  });

  const filters: { label: string; value: InsightFilter }[] = [
    { label: 'All', value: 'all' },
    { label: 'Risks', value: 'risk' },
    { label: 'Opportunities', value: 'opportunity' },
    { label: 'Trends', value: 'trend' },
    { label: 'Entities', value: 'entity' },
  ];

  if (error) {
    return (
      <div className="text-red-500">Failed to load insights. Please try again.</div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Insights</h1>
        <div className="text-sm text-gray-500">
          {data?.total ?? 0} total insights
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {filters.map((f) => (
          <Button
            key={f.value}
            variant={filter === f.value ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      {/* Insights List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : data?.items.length ? (
        <div className="grid gap-4">
          {data.items.map((insight) => (
            <Card key={insight.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium text-gray-900">{insight.title}</h3>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      insight.type === 'risk'
                        ? 'bg-red-100 text-red-800'
                        : insight.type === 'opportunity'
                        ? 'bg-green-100 text-green-800'
                        : insight.type === 'trend'
                        ? 'bg-purple-100 text-purple-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    {insight.type}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600">{insight.description}</p>
                <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
                  <span>Confidence: {(insight.confidence * 100).toFixed(0)}%</span>
                  {insight.severity && (
                    <span className="capitalize">Severity: {insight.severity}</span>
                  )}
                  {insight.documentName && (
                    <span>Source: {insight.documentName}</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-gray-500">
            No insights found.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
