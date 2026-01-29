import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus,
  Search,
  Filter,
  MoreVertical,
  Play,
  Pause,
  Copy,
  Trash2,
  Settings,
  Clock,
  Zap,
  CheckCircle,
  AlertCircle,
  XCircle,
} from 'lucide-react';
import { Button, Input, Card } from '@/components/ui';
import { useAgents, useDeleteAgent, useToggleAgentStatus, useCloneAgent } from '@/hooks/useAgentGeneration';
import type { Agent } from '@/types';

const STATUS_CONFIG = {
  draft: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-100', label: 'Draft' },
  active: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-100', label: 'Active' },
  paused: { icon: Pause, color: 'text-amber-500', bg: 'bg-amber-100', label: 'Paused' },
  error: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-100', label: 'Error' },
};

export default function Agents() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const { data, isLoading, error } = useAgents({
    status: statusFilter === 'all' ? undefined : statusFilter,
  });

  const deleteAgent = useDeleteAgent();
  const toggleStatus = useToggleAgentStatus();
  const cloneAgent = useCloneAgent();

  const agents = data?.items || [];
  const filteredAgents = agents.filter(
    (agent) =>
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.displayName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggleStatus = async (agent: Agent) => {
    const newStatus = agent.status === 'active' ? 'paused' : 'active';
    await toggleStatus.mutateAsync({ id: agent.id, status: newStatus });
  };

  const handleClone = async (agent: Agent) => {
    await cloneAgent.mutateAsync(agent.id);
  };

  const handleDelete = async (agent: Agent) => {
    if (confirm(`Are you sure you want to delete "${agent.displayName}"?`)) {
      await deleteAgent.mutateAsync(agent.id);
    }
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Agents</h1>
          <p className="text-gray-500">Automate workflows with intelligent agents</p>
        </div>
        <Button onClick={() => navigate('/agents/new')}>
          <Plus className="w-4 h-4 mr-2" />
          Create Agent
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search agents..."
            className="pl-10"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="draft">Draft</option>
          <option value="error">Error</option>
        </select>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <Card className="p-6 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to load agents</h3>
          <p className="text-gray-500">Please try again later.</p>
        </Card>
      )}

      {/* Empty state */}
      {!isLoading && !error && filteredAgents.length === 0 && (
        <Card className="p-12 text-center">
          <Zap className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {searchQuery ? 'No agents found' : 'No agents yet'}
          </h3>
          <p className="text-gray-500 mb-6 max-w-md mx-auto">
            {searchQuery
              ? 'Try adjusting your search or filters.'
              : 'Create your first AI agent to automate workflows and get insights.'}
          </p>
          {!searchQuery && (
            <Button onClick={() => navigate('/agents/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Create Your First Agent
            </Button>
          )}
        </Card>
      )}

      {/* Agent list */}
      {!isLoading && !error && filteredAgents.length > 0 && (
        <div className="grid gap-4">
          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              isMenuOpen={selectedAgent === agent.id}
              onMenuToggle={() =>
                setSelectedAgent(selectedAgent === agent.id ? null : agent.id)
              }
              onEdit={() => navigate(`/agents/${agent.id}/edit`)}
              onToggleStatus={() => handleToggleStatus(agent)}
              onClone={() => handleClone(agent)}
              onDelete={() => handleDelete(agent)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface AgentCardProps {
  agent: Agent;
  isMenuOpen: boolean;
  onMenuToggle: () => void;
  onEdit: () => void;
  onToggleStatus: () => void;
  onClone: () => void;
  onDelete: () => void;
}

function AgentCard({
  agent,
  isMenuOpen,
  onMenuToggle,
  onEdit,
  onToggleStatus,
  onClone,
  onDelete,
}: AgentCardProps) {
  const status = STATUS_CONFIG[agent.status];
  const StatusIcon = status.icon;

  return (
    <Card className="p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className={`p-3 rounded-lg ${status.bg}`}>
          <Zap className={`w-6 h-6 ${status.color}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link
              to={`/agents/${agent.id}/edit`}
              className="font-semibold text-gray-900 hover:text-primary-600 truncate"
            >
              {agent.displayName}
            </Link>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${status.bg} ${status.color}`}
            >
              <StatusIcon className="w-3 h-3" />
              {status.label}
            </span>
          </div>

          <p className="text-sm text-gray-500 mb-2 truncate">{agent.description}</p>

          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {agent.trigger.name}
            </span>
            <span>{agent.actions.length} actions</span>
            <span>{agent.runCount} runs</span>
            {agent.lastRunAt && (
              <span>Last run: {new Date(agent.lastRunAt).toLocaleDateString()}</span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {agent.status !== 'draft' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleStatus}
              title={agent.status === 'active' ? 'Pause agent' : 'Activate agent'}
            >
              {agent.status === 'active' ? (
                <Pause className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )}
            </Button>
          )}

          <div className="relative">
            <Button variant="ghost" size="sm" onClick={onMenuToggle}>
              <MoreVertical className="w-4 h-4" />
            </Button>

            {isMenuOpen && (
              <>
                <div className="fixed inset-0" onClick={onMenuToggle} />
                <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10 min-w-[150px]">
                  <button
                    onClick={() => {
                      onMenuToggle();
                      onEdit();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Settings className="w-4 h-4" />
                    Edit
                  </button>
                  <button
                    onClick={() => {
                      onMenuToggle();
                      onClone();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Copy className="w-4 h-4" />
                    Clone
                  </button>
                  <hr className="my-1 border-gray-200" />
                  <button
                    onClick={() => {
                      onMenuToggle();
                      onDelete();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
