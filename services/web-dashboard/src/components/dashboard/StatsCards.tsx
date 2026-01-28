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
