# Task 9.6.2: Approval UI

## Objective

Implement the approval UI components for reviewing, approving, and rejecting agent action requests with detailed context display.

## Prerequisites

- Task 9.6.1 completed (Approval Service)
- React/TypeScript UI framework

## Implementation

### Step 1: Approval Types and API Client

```typescript
// src/features/approvals/types.ts
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled';
export type ApprovalPriority = 'low' | 'medium' | 'high' | 'urgent';
export type ApprovalType = 'action' | 'execution' | 'escalation' | 'sensitive';

export interface ApprovalRequest {
  id: string;
  agentId: string;
  agentName?: string;
  executionId: string | null;
  actionId: string | null;
  approvalType: ApprovalType;
  status: ApprovalStatus;
  priority: ApprovalPriority;
  title: string;
  description: string | null;
  actionSummary: string | null;
  contextData: Record<string, unknown>;
  assignedTo: string | null;
  approvedBy: string | null;
  responseNotes: string | null;
  createdAt: string;
  expiresAt: string | null;
  respondedAt: string | null;
}

export interface ApprovalRule {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  priority: number;
  agentPattern: string | null;
  actionTypes: string[];
  triggerTypes: string[];
  conditions: Record<string, unknown>;
  approvalType: string;
  requiredApprovers: number;
  approverRoles: string[];
  timeoutHours: number;
  createdAt: string;
  updatedAt: string;
}

export interface ApprovalDecision {
  approved: boolean;
  notes?: string;
  modifications?: Record<string, unknown>;
}

export interface ApprovalStats {
  periodDays: number;
  byStatus: Record<string, number>;
  totalRequests: number;
  pendingCount: number;
  averageResponseTimeSeconds: number | null;
  approvalRate: number | null;
}
```

```typescript
// src/features/approvals/api.ts
import { api } from '@/lib/api';
import type {
  ApprovalRequest,
  ApprovalRule,
  ApprovalDecision,
  ApprovalStats
} from './types';

export const approvalsApi = {
  listPending: async (params?: {
    agentId?: string;
    priority?: string;
    limit?: number;
    offset?: number;
  }) => {
    const response = await api.get<{
      approvals: ApprovalRequest[];
      total: number;
    }>('/approvals', { params });
    return response.data;
  },

  getById: async (id: string) => {
    const response = await api.get<ApprovalRequest>(`/approvals/${id}`);
    return response.data;
  },

  approve: async (id: string, decision: ApprovalDecision) => {
    const response = await api.post(`/approvals/${id}/approve`, decision);
    return response.data;
  },

  reject: async (id: string, decision: ApprovalDecision) => {
    const response = await api.post(`/approvals/${id}/reject`, decision);
    return response.data;
  },

  cancel: async (id: string) => {
    const response = await api.post(`/approvals/${id}/cancel`);
    return response.data;
  },

  getStats: async (days?: number) => {
    const response = await api.get<ApprovalStats>('/approvals/stats', {
      params: { days },
    });
    return response.data;
  },

  // Rules
  listRules: async (enabledOnly?: boolean) => {
    const response = await api.get<{ rules: ApprovalRule[]; total: number }>(
      '/approvals/rules',
      { params: { enabled_only: enabledOnly } }
    );
    return response.data;
  },

  createRule: async (rule: Partial<ApprovalRule>) => {
    const response = await api.post<ApprovalRule>('/approvals/rules', rule);
    return response.data;
  },

  updateRule: async (id: string, updates: Partial<ApprovalRule>) => {
    const response = await api.put<ApprovalRule>(`/approvals/rules/${id}`, updates);
    return response.data;
  },

  deleteRule: async (id: string) => {
    const response = await api.delete(`/approvals/rules/${id}`);
    return response.data;
  },
};
```

### Step 2: Approval Queue Component

```tsx
// src/features/approvals/components/ApprovalQueue.tsx
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { approvalsApi } from '../api';
import type { ApprovalRequest, ApprovalPriority } from '../types';
import { ApprovalCard } from './ApprovalCard';
import { ApprovalDetailModal } from './ApprovalDetailModal';

interface ApprovalQueueProps {
  agentId?: string;
}

export const ApprovalQueue: React.FC<ApprovalQueueProps> = ({ agentId }) => {
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<ApprovalPriority | 'all'>('all');
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['approvals', 'pending', agentId, priorityFilter],
    queryFn: () => approvalsApi.listPending({
      agentId,
      priority: priorityFilter !== 'all' ? priorityFilter : undefined,
      limit: 50,
    }),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      approvalsApi.approve(id, { approved: true, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setSelectedApproval(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      approvalsApi.reject(id, { approved: false, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setSelectedApproval(null);
    },
  });

  if (isLoading) {
    return <QueueSkeleton />;
  }

  if (error) {
    return (
      <div className="text-red-600 p-4 bg-red-50 rounded-lg">
        Failed to load approval queue. Please try again.
      </div>
    );
  }

  const priorityCounts = data?.approvals.reduce(
    (acc, approval) => {
      acc[approval.priority] = (acc[approval.priority] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Pending Approvals
          </h2>
          <p className="text-sm text-gray-500">
            {data?.total || 0} requests awaiting your review
          </p>
        </div>

        {/* Priority Filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Filter:</span>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value as ApprovalPriority | 'all')}
            className="rounded-md border-gray-300 text-sm"
          >
            <option value="all">All Priorities</option>
            <option value="urgent">
              Urgent ({priorityCounts?.urgent || 0})
            </option>
            <option value="high">
              High ({priorityCounts?.high || 0})
            </option>
            <option value="medium">
              Medium ({priorityCounts?.medium || 0})
            </option>
            <option value="low">
              Low ({priorityCounts?.low || 0})
            </option>
          </select>
        </div>
      </div>

      {/* Empty State */}
      {data?.approvals.length === 0 && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">
            No pending approvals
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            All caught up! Check back later for new requests.
          </p>
        </div>
      )}

      {/* Approval Cards */}
      <div className="space-y-3">
        {data?.approvals.map((approval) => (
          <ApprovalCard
            key={approval.id}
            approval={approval}
            onView={() => setSelectedApproval(approval)}
            onQuickApprove={() => approveMutation.mutate({ id: approval.id })}
            onQuickReject={() => rejectMutation.mutate({ id: approval.id })}
            isApproving={approveMutation.isPending}
            isRejecting={rejectMutation.isPending}
          />
        ))}
      </div>

      {/* Detail Modal */}
      {selectedApproval && (
        <ApprovalDetailModal
          approval={selectedApproval}
          onClose={() => setSelectedApproval(null)}
          onApprove={(notes, modifications) =>
            approveMutation.mutate({ id: selectedApproval.id, notes })
          }
          onReject={(notes) =>
            rejectMutation.mutate({ id: selectedApproval.id, notes })
          }
          isApproving={approveMutation.isPending}
          isRejecting={rejectMutation.isPending}
        />
      )}
    </div>
  );
};

const QueueSkeleton: React.FC = () => (
  <div className="space-y-4 animate-pulse">
    <div className="h-8 bg-gray-200 rounded w-48" />
    {[1, 2, 3].map((i) => (
      <div key={i} className="h-32 bg-gray-200 rounded" />
    ))}
  </div>
);
```

### Step 3: Approval Card Component

```tsx
// src/features/approvals/components/ApprovalCard.tsx
import React from 'react';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import type { ApprovalRequest } from '../types';

interface ApprovalCardProps {
  approval: ApprovalRequest;
  onView: () => void;
  onQuickApprove: () => void;
  onQuickReject: () => void;
  isApproving: boolean;
  isRejecting: boolean;
}

const priorityColors = {
  urgent: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-gray-100 text-gray-800 border-gray-200',
};

const priorityBorders = {
  urgent: 'border-l-red-500',
  high: 'border-l-orange-500',
  medium: 'border-l-yellow-500',
  low: 'border-l-gray-300',
};

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  approval,
  onView,
  onQuickApprove,
  onQuickReject,
  isApproving,
  isRejecting,
}) => {
  const isExpiringSoon = approval.expiresAt &&
    new Date(approval.expiresAt).getTime() - Date.now() < 3600000; // 1 hour

  return (
    <div
      className={clsx(
        'bg-white rounded-lg border shadow-sm p-4',
        'border-l-4',
        priorityBorders[approval.priority],
        'hover:shadow-md transition-shadow'
      )}
    >
      <div className="flex items-start justify-between">
        {/* Left: Content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-1">
            <span
              className={clsx(
                'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                priorityColors[approval.priority]
              )}
            >
              {approval.priority.toUpperCase()}
            </span>
            <span className="text-xs text-gray-500">
              {approval.approvalType}
            </span>
            {isExpiringSoon && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                Expiring soon
              </span>
            )}
          </div>

          {/* Title */}
          <h3 className="text-sm font-medium text-gray-900 truncate">
            {approval.title}
          </h3>

          {/* Description */}
          {approval.description && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">
              {approval.description}
            </p>
          )}

          {/* Metadata */}
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            {approval.agentName && (
              <span>Agent: {approval.agentName}</span>
            )}
            <span>
              Requested {formatDistanceToNow(new Date(approval.createdAt))} ago
            </span>
            {approval.expiresAt && (
              <span>
                Expires {formatDistanceToNow(new Date(approval.expiresAt))}
              </span>
            )}
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2 ml-4">
          <button
            onClick={onView}
            className="px-3 py-1.5 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
          >
            Review
          </button>
          <button
            onClick={onQuickApprove}
            disabled={isApproving}
            className="px-3 py-1.5 text-sm text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            {isApproving ? 'Approving...' : 'Approve'}
          </button>
          <button
            onClick={onQuickReject}
            disabled={isRejecting}
            className="px-3 py-1.5 text-sm text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50"
          >
            {isRejecting ? 'Rejecting...' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  );
};
```

### Step 4: Approval Detail Modal

```tsx
// src/features/approvals/components/ApprovalDetailModal.tsx
import React, { useState } from 'react';
import { formatDistanceToNow, format } from 'date-fns';
import type { ApprovalRequest } from '../types';

interface ApprovalDetailModalProps {
  approval: ApprovalRequest;
  onClose: () => void;
  onApprove: (notes?: string, modifications?: Record<string, unknown>) => void;
  onReject: (notes?: string) => void;
  isApproving: boolean;
  isRejecting: boolean;
}

export const ApprovalDetailModal: React.FC<ApprovalDetailModalProps> = ({
  approval,
  onClose,
  onApprove,
  onReject,
  isApproving,
  isRejecting,
}) => {
  const [notes, setNotes] = useState('');
  const [showModifications, setShowModifications] = useState(false);
  const [modifications, setModifications] = useState<Record<string, unknown>>({});

  const handleApprove = () => {
    onApprove(
      notes || undefined,
      Object.keys(modifications).length > 0 ? modifications : undefined
    );
  };

  const handleReject = () => {
    onReject(notes || undefined);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                Review Approval Request
              </h2>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-500"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="px-6 py-4 space-y-6">
            {/* Request Info */}
            <div>
              <h3 className="text-sm font-medium text-gray-900 mb-2">
                Request Details
              </h3>
              <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Title</span>
                  <span className="text-sm font-medium">{approval.title}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Priority</span>
                  <span className="text-sm font-medium capitalize">{approval.priority}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Type</span>
                  <span className="text-sm font-medium capitalize">{approval.approvalType}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Requested</span>
                  <span className="text-sm">
                    {format(new Date(approval.createdAt), 'PPpp')}
                  </span>
                </div>
                {approval.expiresAt && (
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Expires</span>
                    <span className="text-sm">
                      {formatDistanceToNow(new Date(approval.expiresAt))}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Description */}
            {approval.description && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Description
                </h3>
                <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-4">
                  {approval.description}
                </p>
              </div>
            )}

            {/* Action Summary */}
            {approval.actionSummary && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Action Summary
                </h3>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <pre className="text-sm text-blue-800 whitespace-pre-wrap">
                    {approval.actionSummary}
                  </pre>
                </div>
              </div>
            )}

            {/* Context Data */}
            {Object.keys(approval.contextData).length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Context
                </h3>
                <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                  <pre className="text-sm text-green-400">
                    {JSON.stringify(approval.contextData, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Notes (optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add any notes about your decision..."
                rows={3}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </div>

            {/* Modifications Toggle */}
            <div>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showModifications}
                  onChange={(e) => setShowModifications(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">
                  Approve with modifications
                </span>
              </label>
              {showModifications && (
                <div className="mt-2">
                  <textarea
                    value={JSON.stringify(modifications, null, 2)}
                    onChange={(e) => {
                      try {
                        setModifications(JSON.parse(e.target.value));
                      } catch {
                        // Invalid JSON, keep current
                      }
                    }}
                    placeholder='{"field": "modified_value"}'
                    rows={4}
                    className="w-full font-mono text-sm rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              onClick={handleReject}
              disabled={isRejecting}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50"
            >
              {isRejecting ? 'Rejecting...' : 'Reject'}
            </button>
            <button
              onClick={handleApprove}
              disabled={isApproving}
              className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {isApproving ? 'Approving...' : 'Approve'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
```

### Step 5: Approval Rules Manager

```tsx
// src/features/approvals/components/ApprovalRulesManager.tsx
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { approvalsApi } from '../api';
import type { ApprovalRule } from '../types';
import { RuleEditor } from './RuleEditor';

export const ApprovalRulesManager: React.FC = () => {
  const [editingRule, setEditingRule] = useState<ApprovalRule | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['approvalRules'],
    queryFn: () => approvalsApi.listRules(),
  });

  const createMutation = useMutation({
    mutationFn: approvalsApi.createRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvalRules'] });
      setIsCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<ApprovalRule> }) =>
      approvalsApi.updateRule(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvalRules'] });
      setEditingRule(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: approvalsApi.deleteRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvalRules'] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      approvalsApi.updateRule(id, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvalRules'] });
    },
  });

  if (isLoading) {
    return <div className="animate-pulse h-64 bg-gray-200 rounded" />;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Approval Rules
          </h2>
          <p className="text-sm text-gray-500">
            Configure when agent actions require human approval
          </p>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          Create Rule
        </button>
      </div>

      {/* Rules List */}
      <div className="space-y-3">
        {data?.rules.map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            onEdit={() => setEditingRule(rule)}
            onDelete={() => deleteMutation.mutate(rule.id)}
            onToggle={(enabled) =>
              toggleMutation.mutate({ id: rule.id, enabled })
            }
            isDeleting={deleteMutation.isPending}
          />
        ))}

        {data?.rules.length === 0 && (
          <div className="text-center py-8 bg-gray-50 rounded-lg">
            <p className="text-gray-500">No approval rules configured</p>
            <button
              onClick={() => setIsCreating(true)}
              className="mt-2 text-blue-600 hover:text-blue-700"
            >
              Create your first rule
            </button>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(isCreating || editingRule) && (
        <RuleEditor
          rule={editingRule}
          onSave={(ruleData) => {
            if (editingRule) {
              updateMutation.mutate({
                id: editingRule.id,
                updates: ruleData,
              });
            } else {
              createMutation.mutate(ruleData);
            }
          }}
          onClose={() => {
            setIsCreating(false);
            setEditingRule(null);
          }}
          isSaving={createMutation.isPending || updateMutation.isPending}
        />
      )}
    </div>
  );
};

interface RuleCardProps {
  rule: ApprovalRule;
  onEdit: () => void;
  onDelete: () => void;
  onToggle: (enabled: boolean) => void;
  isDeleting: boolean;
}

const RuleCard: React.FC<RuleCardProps> = ({
  rule,
  onEdit,
  onDelete,
  onToggle,
  isDeleting,
}) => {
  return (
    <div className={`bg-white border rounded-lg p-4 ${!rule.enabled ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-gray-900">{rule.name}</h3>
            <span className="text-xs text-gray-500">
              Priority: {rule.priority}
            </span>
          </div>
          {rule.description && (
            <p className="text-sm text-gray-500 mt-1">{rule.description}</p>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {rule.actionTypes.map((type) => (
              <span
                key={type}
                className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
              >
                {type}
              </span>
            ))}
            {rule.agentPattern && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                Pattern: {rule.agentPattern}
              </span>
            )}
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
              {rule.approvalType}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={rule.enabled}
              onChange={(e) => onToggle(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
          <button
            onClick={onEdit}
            className="p-2 text-gray-400 hover:text-gray-500"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            onClick={onDelete}
            disabled={isDeleting}
            className="p-2 text-red-400 hover:text-red-500"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};
```

### Step 6: Approval Stats Dashboard

```tsx
// src/features/approvals/components/ApprovalStats.tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { approvalsApi } from '../api';

interface ApprovalStatsProps {
  days?: number;
}

export const ApprovalStats: React.FC<ApprovalStatsProps> = ({ days = 7 }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['approvalStats', days],
    queryFn: () => approvalsApi.getStats(days),
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="animate-pulse h-24 bg-gray-200 rounded-lg" />
        ))}
      </div>
    );
  }

  if (!data) return null;

  const formatTime = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  const formatPercent = (rate: number | null) => {
    if (rate === null) return 'N/A';
    return `${(rate * 100).toFixed(1)}%`;
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <StatCard
        title="Pending"
        value={data.pendingCount}
        subtitle="Awaiting review"
        color="yellow"
      />
      <StatCard
        title="Total Requests"
        value={data.totalRequests}
        subtitle={`Last ${data.periodDays} days`}
        color="blue"
      />
      <StatCard
        title="Avg Response Time"
        value={formatTime(data.averageResponseTimeSeconds)}
        subtitle="Time to decision"
        color="green"
      />
      <StatCard
        title="Approval Rate"
        value={formatPercent(data.approvalRate)}
        subtitle="Approved / Total"
        color="purple"
      />
    </div>
  );
};

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  color: 'yellow' | 'blue' | 'green' | 'purple';
}

const StatCard: React.FC<StatCardProps> = ({ title, value, subtitle, color }) => {
  const colorClasses = {
    yellow: 'bg-yellow-50 border-yellow-200',
    blue: 'bg-blue-50 border-blue-200',
    green: 'bg-green-50 border-green-200',
    purple: 'bg-purple-50 border-purple-200',
  };

  return (
    <div className={`rounded-lg border p-4 ${colorClasses[color]}`}>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
    </div>
  );
};
```

## Test Cases

```typescript
// src/features/approvals/__tests__/ApprovalQueue.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApprovalQueue } from '../components/ApprovalQueue';
import { approvalsApi } from '../api';

jest.mock('../api');

const mockApprovals = [
  {
    id: '1',
    agentId: 'agent-1',
    agentName: 'Email Agent',
    executionId: 'exec-1',
    actionId: 'action-1',
    approvalType: 'action',
    status: 'pending',
    priority: 'high',
    title: 'Send email to customers',
    description: 'Agent wants to send 100 emails',
    actionSummary: null,
    contextData: {},
    assignedTo: null,
    approvedBy: null,
    responseNotes: null,
    createdAt: new Date().toISOString(),
    expiresAt: new Date(Date.now() + 86400000).toISOString(),
    respondedAt: null,
  },
];

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('ApprovalQueue', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders pending approvals', async () => {
    (approvalsApi.listPending as jest.Mock).mockResolvedValue({
      approvals: mockApprovals,
      total: 1,
    });

    render(<ApprovalQueue />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Send email to customers')).toBeInTheDocument();
    });

    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('Email Agent')).toBeTruthy();
  });

  it('shows empty state when no approvals', async () => {
    (approvalsApi.listPending as jest.Mock).mockResolvedValue({
      approvals: [],
      total: 0,
    });

    render(<ApprovalQueue />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No pending approvals')).toBeInTheDocument();
    });
  });

  it('filters by priority', async () => {
    (approvalsApi.listPending as jest.Mock).mockResolvedValue({
      approvals: mockApprovals,
      total: 1,
    });

    render(<ApprovalQueue />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Send email to customers')).toBeInTheDocument();
    });

    const filter = screen.getByRole('combobox');
    fireEvent.change(filter, { target: { value: 'urgent' } });

    expect(approvalsApi.listPending).toHaveBeenCalledWith(
      expect.objectContaining({ priority: 'urgent' })
    );
  });

  it('quick approves an approval', async () => {
    (approvalsApi.listPending as jest.Mock).mockResolvedValue({
      approvals: mockApprovals,
      total: 1,
    });
    (approvalsApi.approve as jest.Mock).mockResolvedValue({});

    render(<ApprovalQueue />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Approve'));

    await waitFor(() => {
      expect(approvalsApi.approve).toHaveBeenCalledWith('1', {
        approved: true,
        notes: undefined,
      });
    });
  });

  it('opens detail modal on review click', async () => {
    (approvalsApi.listPending as jest.Mock).mockResolvedValue({
      approvals: mockApprovals,
      total: 1,
    });

    render(<ApprovalQueue />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Review')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Review'));

    await waitFor(() => {
      expect(screen.getByText('Review Approval Request')).toBeInTheDocument();
    });
  });
});

describe('ApprovalDetailModal', () => {
  it('displays approval details', async () => {
    (approvalsApi.listPending as jest.Mock).mockResolvedValue({
      approvals: mockApprovals,
      total: 1,
    });

    render(<ApprovalQueue />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Review')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Review'));

    await waitFor(() => {
      expect(screen.getByText('Request Details')).toBeInTheDocument();
      expect(screen.getByText('Send email to customers')).toBeInTheDocument();
    });
  });

  it('allows adding notes before approval', async () => {
    (approvalsApi.listPending as jest.Mock).mockResolvedValue({
      approvals: mockApprovals,
      total: 1,
    });
    (approvalsApi.approve as jest.Mock).mockResolvedValue({});

    render(<ApprovalQueue />, { wrapper: createWrapper() });

    await waitFor(() => {
      fireEvent.click(screen.getByText('Review'));
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Add any notes/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Add any notes/), {
      target: { value: 'Approved for sending' },
    });

    fireEvent.click(screen.getAllByText('Approve')[1]); // Modal approve button

    await waitFor(() => {
      expect(approvalsApi.approve).toHaveBeenCalledWith('1', {
        approved: true,
        notes: 'Approved for sending',
      });
    });
  });
});
```

## Verification Steps

1. **Run component tests:**
   ```bash
   npm test -- --testPathPattern=approvals
   ```

2. **Test approval queue:**
   - Navigate to /approvals
   - Verify pending approvals are displayed
   - Test priority filtering
   - Test quick approve/reject
   - Verify refresh interval works

3. **Test detail modal:**
   - Click "Review" on an approval
   - Verify all details are displayed
   - Add notes and approve
   - Test modifications feature

4. **Test rules manager:**
   - Navigate to /approvals/rules
   - Create a new rule
   - Toggle rule enabled/disabled
   - Edit and delete rules

## Next Task

Proceed to `task-9.6.3-agent-permissions.md` for implementing agent permissions.
