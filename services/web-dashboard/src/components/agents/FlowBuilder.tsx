import { useCallback, useState, useMemo } from 'react';
import {
  Plus,
  Trash2,
  Settings,
  Play,
  ChevronRight,
  Mail,
  MessageSquare,
  FileText,
  Clock,
  Zap,
  Filter,
  GitBranch,
} from 'lucide-react';
import { Button, Card } from '@/components/ui';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';
import type { TriggerDefinition, ActionDefinition, ConditionDefinition } from '@/types';

interface FlowBuilderProps {
  onNodeSelect?: (nodeId: string, type: 'trigger' | 'action' | 'condition') => void;
}

const TRIGGER_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  slack: MessageSquare,
  document: FileText,
  schedule: Clock,
  webhook: Zap,
};

const ACTION_ICONS: Record<string, typeof Mail> = {
  summarize: FileText,
  send_message: MessageSquare,
  send_email: Mail,
  create_ticket: FileText,
  filter: Filter,
  transform: GitBranch,
};

export function FlowBuilder({ onNodeSelect }: FlowBuilderProps) {
  const {
    trigger,
    actions,
    conditions,
    selectedNodeId,
    isConnecting,
    connectionSource,
    setTrigger,
    addAction,
    removeAction,
    addCondition,
    removeCondition,
    selectNode,
    startConnecting,
    finishConnecting,
    cancelConnecting,
  } = useAgentBuilderStore();

  const [showAddMenu, setShowAddMenu] = useState<'trigger' | 'action' | 'condition' | null>(null);

  const handleNodeClick = useCallback(
    (nodeId: string, type: 'trigger' | 'action' | 'condition') => {
      if (isConnecting && connectionSource !== nodeId && type === 'action') {
        finishConnecting(nodeId);
      } else {
        selectNode(nodeId);
        onNodeSelect?.(nodeId, type);
      }
    },
    [isConnecting, connectionSource, finishConnecting, selectNode, onNodeSelect]
  );

  const handleAddTrigger = useCallback(
    (type: string) => {
      const newTrigger: TriggerDefinition = {
        id: `trigger-${Date.now()}`,
        type,
        name: `${type.charAt(0).toUpperCase() + type.slice(1)} Trigger`,
        config: {},
      };
      setTrigger(newTrigger);
      setShowAddMenu(null);
    },
    [setTrigger]
  );

  const handleAddAction = useCallback(
    (type: string) => {
      const newAction: ActionDefinition = {
        id: `action-${Date.now()}`,
        type,
        name: `${type.replace('_', ' ').charAt(0).toUpperCase() + type.replace('_', ' ').slice(1)}`,
        config: {},
        dependsOn: actions.length > 0 ? [actions[actions.length - 1].id] : [],
        order: actions.length,
      };
      addAction(newAction);
      setShowAddMenu(null);
    },
    [actions, addAction]
  );

  const handleAddCondition = useCallback(
    (expression: string) => {
      const newCondition: ConditionDefinition = {
        id: `condition-${Date.now()}`,
        expression,
        description: expression,
      };
      addCondition(newCondition);
      setShowAddMenu(null);
    },
    [addCondition]
  );

  // Build flow nodes for rendering
  const flowNodes = useMemo(() => {
    const nodes: Array<{
      id: string;
      type: 'trigger' | 'action' | 'condition';
      data: TriggerDefinition | ActionDefinition | ConditionDefinition;
      connections: string[];
    }> = [];

    if (trigger) {
      nodes.push({
        id: trigger.id,
        type: 'trigger',
        data: trigger,
        connections: actions.length > 0 ? [actions[0].id] : [],
      });
    }

    // Add conditions after trigger
    conditions.forEach((condition) => {
      nodes.push({
        id: condition.id,
        type: 'condition',
        data: condition,
        connections: [],
      });
    });

    // Add actions
    actions.forEach((action) => {
      nodes.push({
        id: action.id,
        type: 'action',
        data: action,
        connections: action.dependsOn,
      });
    });

    return nodes;
  }, [trigger, actions, conditions]);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-4 border-b border-gray-200 bg-white">
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddMenu(showAddMenu === 'trigger' ? null : 'trigger')}
            disabled={!!trigger}
          >
            <Plus className="w-4 h-4 mr-1" />
            Trigger
          </Button>
          {showAddMenu === 'trigger' && (
            <AddMenu
              items={[
                { id: 'email', label: 'Email Received', icon: Mail },
                { id: 'slack', label: 'Slack Message', icon: MessageSquare },
                { id: 'document', label: 'Document Added', icon: FileText },
                { id: 'schedule', label: 'Schedule', icon: Clock },
                { id: 'webhook', label: 'Webhook', icon: Zap },
              ]}
              onSelect={handleAddTrigger}
              onClose={() => setShowAddMenu(null)}
            />
          )}
        </div>

        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddMenu(showAddMenu === 'action' ? null : 'action')}
          >
            <Plus className="w-4 h-4 mr-1" />
            Action
          </Button>
          {showAddMenu === 'action' && (
            <AddMenu
              items={[
                { id: 'summarize', label: 'Summarize', icon: FileText },
                { id: 'send_message', label: 'Send Message', icon: MessageSquare },
                { id: 'send_email', label: 'Send Email', icon: Mail },
                { id: 'create_ticket', label: 'Create Ticket', icon: FileText },
                { id: 'filter', label: 'Filter', icon: Filter },
                { id: 'transform', label: 'Transform', icon: GitBranch },
              ]}
              onSelect={handleAddAction}
              onClose={() => setShowAddMenu(null)}
            />
          )}
        </div>

        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddMenu(showAddMenu === 'condition' ? null : 'condition')}
          >
            <Plus className="w-4 h-4 mr-1" />
            Condition
          </Button>
          {showAddMenu === 'condition' && (
            <AddMenu
              items={[
                { id: 'contains("urgent")', label: 'Contains keyword', icon: Filter },
                { id: 'sender == "@company.com"', label: 'From sender', icon: Mail },
                { id: 'confidence > 0.8', label: 'High confidence', icon: Zap },
              ]}
              onSelect={handleAddCondition}
              onClose={() => setShowAddMenu(null)}
            />
          )}
        </div>

        <div className="flex-1" />

        {isConnecting && (
          <Button variant="ghost" size="sm" onClick={cancelConnecting}>
            Cancel Connection
          </Button>
        )}
      </div>

      {/* Canvas */}
      <div
        className="flex-1 bg-gray-50 p-8 overflow-auto"
        onClick={() => {
          selectNode(null);
          if (isConnecting) cancelConnecting();
        }}
      >
        {flowNodes.length === 0 ? (
          <EmptyState onAddTrigger={() => setShowAddMenu('trigger')} />
        ) : (
          <div className="flex flex-col items-center gap-4">
            {/* Trigger */}
            {trigger && (
              <FlowNode
                id={trigger.id}
                type="trigger"
                name={trigger.name}
                icon={TRIGGER_ICONS[trigger.type] || Zap}
                isSelected={selectedNodeId === trigger.id}
                onClick={() => handleNodeClick(trigger.id, 'trigger')}
                onDelete={() => setTrigger(null)}
                onConnect={() => startConnecting(trigger.id)}
                isConnecting={isConnecting}
                isConnectionSource={connectionSource === trigger.id}
              />
            )}

            {/* Connector */}
            {trigger && (actions.length > 0 || conditions.length > 0) && (
              <Connector />
            )}

            {/* Conditions */}
            {conditions.map((condition) => (
              <div key={condition.id} className="flex flex-col items-center gap-4">
                <FlowNode
                  id={condition.id}
                  type="condition"
                  name={condition.description}
                  icon={Filter}
                  isSelected={selectedNodeId === condition.id}
                  onClick={() => handleNodeClick(condition.id, 'condition')}
                  onDelete={() => removeCondition(condition.id)}
                  isConnecting={isConnecting}
                  isConnectionSource={false}
                />
                <Connector />
              </div>
            ))}

            {/* Actions */}
            {actions.map((action, index) => (
              <div key={action.id} className="flex flex-col items-center gap-4">
                <FlowNode
                  id={action.id}
                  type="action"
                  name={action.name}
                  icon={ACTION_ICONS[action.type] || Zap}
                  isSelected={selectedNodeId === action.id}
                  onClick={() => handleNodeClick(action.id, 'action')}
                  onDelete={() => removeAction(action.id)}
                  onConnect={() => startConnecting(action.id)}
                  isConnecting={isConnecting}
                  isConnectionSource={connectionSource === action.id}
                  canReceiveConnection={isConnecting && connectionSource !== action.id}
                />
                {index < actions.length - 1 && <Connector />}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface FlowNodeProps {
  id: string;
  type: 'trigger' | 'action' | 'condition';
  name: string;
  icon: typeof Mail;
  isSelected: boolean;
  onClick: () => void;
  onDelete: () => void;
  onConnect?: () => void;
  isConnecting: boolean;
  isConnectionSource: boolean;
  canReceiveConnection?: boolean;
}

function FlowNode({
  id,
  type,
  name,
  icon: Icon,
  isSelected,
  onClick,
  onDelete,
  onConnect,
  isConnecting,
  isConnectionSource,
  canReceiveConnection,
}: FlowNodeProps) {
  const colors = {
    trigger: 'bg-blue-50 border-blue-200 text-blue-700',
    action: 'bg-green-50 border-green-200 text-green-700',
    condition: 'bg-amber-50 border-amber-200 text-amber-700',
  };

  const selectedColors = {
    trigger: 'ring-blue-500',
    action: 'ring-green-500',
    condition: 'ring-amber-500',
  };

  return (
    <div
      className={`
        relative flex items-center gap-3 px-4 py-3 rounded-lg border-2 cursor-pointer
        transition-all min-w-[200px]
        ${colors[type]}
        ${isSelected ? `ring-2 ${selectedColors[type]}` : ''}
        ${isConnectionSource ? 'ring-2 ring-primary-500 ring-offset-2' : ''}
        ${canReceiveConnection ? 'ring-2 ring-dashed ring-primary-400' : ''}
      `}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <div className="p-2 bg-white rounded-lg shadow-sm">
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1">
        <p className="text-xs uppercase tracking-wide opacity-75">{type}</p>
        <p className="font-medium">{name}</p>
      </div>
      <div className="flex items-center gap-1">
        {onConnect && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onConnect();
            }}
            className="p-1.5 rounded hover:bg-white/50"
            title="Connect to action"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="p-1.5 rounded hover:bg-white/50 text-red-500"
          title="Delete"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function Connector() {
  return (
    <div className="flex flex-col items-center">
      <div className="w-0.5 h-6 bg-gray-300" />
      <div className="w-2 h-2 rounded-full bg-gray-300" />
      <div className="w-0.5 h-6 bg-gray-300" />
    </div>
  );
}

interface AddMenuProps {
  items: Array<{ id: string; label: string; icon: typeof Mail }>;
  onSelect: (id: string) => void;
  onClose: () => void;
}

function AddMenu({ items, onSelect, onClose }: AddMenuProps) {
  return (
    <>
      <div className="fixed inset-0" onClick={onClose} />
      <div className="absolute top-full left-0 mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10 min-w-[180px]">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              <Icon className="w-4 h-4 text-gray-400" />
              {item.label}
            </button>
          );
        })}
      </div>
    </>
  );
}

interface EmptyStateProps {
  onAddTrigger: () => void;
}

function EmptyState({ onAddTrigger }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="p-4 bg-gray-100 rounded-full mb-4">
        <Play className="w-8 h-8 text-gray-400" />
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">
        Start Building Your Agent
      </h3>
      <p className="text-gray-500 mb-6 max-w-md">
        Add a trigger to start, then add actions to define what your agent should do.
      </p>
      <Button onClick={onAddTrigger}>
        <Plus className="w-4 h-4 mr-2" />
        Add Trigger
      </Button>
    </div>
  );
}

export default FlowBuilder;
