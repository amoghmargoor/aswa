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
