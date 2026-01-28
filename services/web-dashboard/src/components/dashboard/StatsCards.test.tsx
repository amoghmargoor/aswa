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
