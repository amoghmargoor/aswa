# Task 9.3.4: Agent Editor

## Objective

Implement the agent detail and editor page for viewing, editing, and managing existing agents.

## Prerequisites

- Task 9.3.1-9.3.3 completed

## Implementation

### Step 1: Agent Detail Page

```tsx
// services/web-dashboard/src/pages/agents/[id].tsx
import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tab } from '@headlessui/react';
import {
  PlayIcon,
  PauseIcon,
  TrashIcon,
  PencilIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

import { apiClient } from '../../lib/apiClient';
import { AgentDefinitionViewer } from '../../components/agents/AgentDefinitionViewer';
import { ExecutionHistory } from '../../components/agents/ExecutionHistory';
import { AgentSettings } from '../../components/agents/AgentSettings';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';

export function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);

  const { data: agent, isLoading } = useQuery({
    queryKey: ['agent', id],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/agents/${id}`);
      return response.data;
    },
  });

  const updateStatus = useMutation({
    mutationFn: async (status: string) => {
      await apiClient.put(`/api/v1/agents/${id}`, { status });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent', id] });
    },
  });

  const deleteAgent = useMutation({
    mutationFn: async () => {
      await apiClient.delete(`/api/v1/agents/${id}`);
    },
    onSuccess: () => {
      navigate('/agents');
    },
  });

  if (isLoading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  if (!agent) {
    return <div className="text-center py-12">Agent not found</div>;
  }

  const isActive = agent.status === 'active';

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-gray-900">{agent.displayName}</h1>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
              agent.status === 'active' ? 'bg-green-100 text-green-800' :
              agent.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
              'bg-gray-100 text-gray-800'
            }`}>
              {agent.status.toUpperCase()}
            </span>
          </div>
          <p className="mt-1 text-gray-600">{agent.description}</p>
          <div className="flex items-center mt-2 text-sm text-gray-500 space-x-4">
            <span className="flex items-center">
              <ClockIcon className="w-4 h-4 mr-1" />
              Created {new Date(agent.createdAt).toLocaleDateString()}
            </span>
            <span className="flex items-center">
              <CheckCircleIcon className="w-4 h-4 mr-1 text-green-500" />
              {agent.successCount} successful
            </span>
            <span className="flex items-center">
              <XCircleIcon className="w-4 h-4 mr-1 text-red-500" />
              {agent.failureCount} failed
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => updateStatus.mutate(isActive ? 'paused' : 'active')}
            className={`flex items-center px-4 py-2 rounded-lg font-medium ${
              isActive
                ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                : 'bg-green-100 text-green-700 hover:bg-green-200'
            }`}
          >
            {isActive ? (
              <>
                <PauseIcon className="w-5 h-5 mr-2" />
                Pause
              </>
            ) : (
              <>
                <PlayIcon className="w-5 h-5 mr-2" />
                Activate
              </>
            )}
          </button>
          <button
            onClick={() => navigate(`/agents/${id}/edit`)}
            className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            <PencilIcon className="w-5 h-5 mr-2" />
            Edit
          </button>
          <button
            onClick={() => setShowDeleteDialog(true)}
            className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
          >
            <TrashIcon className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <Tab.Group>
        <Tab.List className="flex space-x-1 border-b">
          {['Definition', 'Executions', 'Settings'].map((tab) => (
            <Tab
              key={tab}
              className={({ selected }) =>
                `px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                  selected
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`
              }
            >
              {tab}
            </Tab>
          ))}
        </Tab.List>
        <Tab.Panels className="mt-6">
          <Tab.Panel>
            <AgentDefinitionViewer definition={agent.definition} />
          </Tab.Panel>
          <Tab.Panel>
            <ExecutionHistory agentId={id!} />
          </Tab.Panel>
          <Tab.Panel>
            <AgentSettings agent={agent} />
          </Tab.Panel>
        </Tab.Panels>
      </Tab.Group>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        onConfirm={() => deleteAgent.mutate()}
        title="Delete Agent"
        message={`Are you sure you want to delete "${agent.displayName}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}
```

### Step 2: Definition Viewer

```tsx
// services/web-dashboard/src/components/agents/AgentDefinitionViewer.tsx
import React, { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import yaml from 'js-yaml';

interface Props {
  definition: any;
}

export function AgentDefinitionViewer({ definition }: Props) {
  const [viewMode, setViewMode] = useState<'visual' | 'yaml'>('visual');

  return (
    <div className="bg-white rounded-lg border">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <h3 className="font-medium text-gray-900">Agent Definition</h3>
        <div className="flex rounded-lg border overflow-hidden">
          <button
            onClick={() => setViewMode('visual')}
            className={`px-3 py-1 text-sm ${
              viewMode === 'visual'
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-600'
            }`}
          >
            Visual
          </button>
          <button
            onClick={() => setViewMode('yaml')}
            className={`px-3 py-1 text-sm ${
              viewMode === 'yaml'
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-600'
            }`}
          >
            YAML
          </button>
        </div>
      </div>

      {viewMode === 'visual' ? (
        <div className="p-4 space-y-4">
          {/* Trigger */}
          <DefinitionSection title="Trigger" icon="⚡">
            <div className="p-3 bg-indigo-50 rounded-lg">
              <p className="font-medium text-indigo-700 capitalize">
                {definition.trigger.type}
              </p>
              {Object.keys(definition.trigger.config || {}).length > 0 && (
                <pre className="mt-2 text-xs text-indigo-600">
                  {JSON.stringify(definition.trigger.config, null, 2)}
                </pre>
              )}
            </div>
          </DefinitionSection>

          {/* Actions */}
          <DefinitionSection title={`Actions (${definition.actions?.length || 0})`} icon="⚙️">
            <div className="space-y-2">
              {definition.actions?.map((action: any, index: number) => (
                <div key={action.id || index} className="p-3 bg-green-50 rounded-lg flex items-center">
                  <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-green-100 rounded-full text-xs font-medium text-green-700 mr-3">
                    {index + 1}
                  </span>
                  <div className="flex-1">
                    <p className="font-medium text-green-700 capitalize">
                      {action.type}
                    </p>
                    {action.description && (
                      <p className="text-sm text-green-600">{action.description}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </DefinitionSection>

          {/* Approval */}
          <DefinitionSection title="Approval" icon="✅">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="font-medium text-gray-700">
                Mode: <span className="capitalize">{definition.approval?.mode || 'review'}</span>
              </p>
              <p className="text-sm text-gray-600 mt-1">
                Timeout: {definition.approval?.timeout_hours || 24} hours
              </p>
            </div>
          </DefinitionSection>
        </div>
      ) : (
        <div className="p-4">
          <SyntaxHighlighter language="yaml" style={docco} className="rounded-lg">
            {yaml.dump(definition)}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  );
}

function DefinitionSection({ title, icon, children }: {
  title: string;
  icon: string;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center w-full text-left mb-2"
      >
        {isOpen ? (
          <ChevronDownIcon className="w-4 h-4 mr-2 text-gray-400" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 mr-2 text-gray-400" />
        )}
        <span className="mr-2">{icon}</span>
        <span className="font-medium text-gray-900">{title}</span>
      </button>
      {isOpen && <div className="ml-6">{children}</div>}
    </div>
  );
}
```

### Step 3: Execution History

```tsx
// services/web-dashboard/src/components/agents/ExecutionHistory.tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { CheckCircleIcon, XCircleIcon, ClockIcon } from '@heroicons/react/24/outline';
import { apiClient } from '../../lib/apiClient';

interface Props {
  agentId: string;
}

export function ExecutionHistory({ agentId }: Props) {
  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions', agentId],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/executions?agent_id=${agentId}`);
      return response.data.executions;
    },
  });

  if (isLoading) {
    return <div>Loading executions...</div>;
  }

  if (!executions?.length) {
    return (
      <div className="text-center py-12 bg-gray-50 rounded-lg">
        <ClockIcon className="w-12 h-12 mx-auto text-gray-400 mb-4" />
        <p className="text-gray-600">No executions yet</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Status
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Trigger
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Started
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Duration
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {executions.map((execution: any) => (
            <tr key={execution.id} className="hover:bg-gray-50">
              <td className="px-6 py-4">
                <StatusBadge status={execution.status} />
              </td>
              <td className="px-6 py-4 text-sm text-gray-900 capitalize">
                {execution.triggerType.replace(/_/g, ' ')}
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">
                {format(new Date(execution.startedAt), 'MMM d, h:mm a')}
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">
                {execution.durationMs ? `${(execution.durationMs / 1000).toFixed(2)}s` : '-'}
              </td>
              <td className="px-6 py-4">
                <button className="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
                  View Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    completed: { icon: CheckCircleIcon, color: 'green', label: 'Completed' },
    failed: { icon: XCircleIcon, color: 'red', label: 'Failed' },
    running: { icon: ClockIcon, color: 'blue', label: 'Running' },
    pending: { icon: ClockIcon, color: 'gray', label: 'Pending' },
  }[status] || { icon: ClockIcon, color: 'gray', label: status };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-${config.color}-100 text-${config.color}-800`}>
      <config.icon className="w-3 h-3 mr-1" />
      {config.label}
    </span>
  );
}
```

## Test Cases

```typescript
describe('AgentDetailPage', () => {
  it('displays agent information', async () => {
    render(<AgentDetailPage />);
    await waitFor(() => {
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
    });
  });

  it('allows toggling agent status', async () => {
    render(<AgentDetailPage />);
    const toggleButton = await screen.findByRole('button', { name: /pause|activate/i });
    expect(toggleButton).toBeInTheDocument();
  });

  it('shows execution history', async () => {
    render(<AgentDetailPage />);
    await waitFor(() => {
      expect(screen.getByText('Executions')).toBeInTheDocument();
    });
  });
});
```

## Next Task

Proceed to `task-9.3.5-yaml-editor.md` for the YAML editor for power users.
