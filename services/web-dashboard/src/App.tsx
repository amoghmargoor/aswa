import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from '@/components/layout';
import { ErrorBoundary } from '@/components/common';
import Dashboard from '@/pages/Dashboard';
import Query from '@/pages/Query';
import Insights from '@/pages/Insights';
import Settings from '@/pages/Settings';
import Agents from '@/pages/Agents';
import AgentBuilder from '@/pages/AgentBuilder';
import { useAuth } from '@/hooks/useAuth';

function App() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/query" element={<Query />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/agents/new" element={<AgentBuilder />} />
          <Route path="/agents/:id/edit" element={<AgentBuilder />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </ErrorBoundary>
  );
}

export default App;
