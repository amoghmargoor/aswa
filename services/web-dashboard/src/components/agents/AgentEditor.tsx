import { useState, useCallback, useMemo } from 'react';
import {
  X,
  Save,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  AlertCircle,
  Info,
} from 'lucide-react';
import { Button, Input, Card } from '@/components/ui';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';
import type { TriggerDefinition, ActionDefinition, ConditionDefinition } from '@/types';

interface AgentEditorProps {
  nodeId: string;
  nodeType: 'trigger' | 'action' | 'condition';
  onClose: () => void;
}

// Schema definitions for configuration options
const TRIGGER_SCHEMAS: Record<string, ConfigField[]> = {
  email: [
    { name: 'from_filter', label: 'From (filter)', type: 'string', placeholder: 'e.g., @company.com' },
    { name: 'subject_filter', label: 'Subject contains', type: 'string', placeholder: 'e.g., urgent' },
    { name: 'folder', label: 'Folder', type: 'select', options: ['inbox', 'all', 'custom'] },
  ],
  slack: [
    { name: 'channel', label: 'Channel', type: 'string', placeholder: '#channel-name' },
    { name: 'mentions_only', label: 'Only when mentioned', type: 'boolean' },
    { name: 'keywords', label: 'Keywords', type: 'array', placeholder: 'Add keyword' },
  ],
  document: [
    { name: 'source', label: 'Source', type: 'select', options: ['any', 'drive', 'sharepoint', 'upload'] },
    { name: 'file_types', label: 'File types', type: 'multiselect', options: ['pdf', 'docx', 'xlsx', 'pptx'] },
  ],
  schedule: [
    { name: 'frequency', label: 'Frequency', type: 'select', options: ['hourly', 'daily', 'weekly', 'monthly'] },
    { name: 'time', label: 'Time', type: 'time' },
    { name: 'timezone', label: 'Timezone', type: 'string', placeholder: 'UTC' },
  ],
  webhook: [
    { name: 'path', label: 'Path', type: 'string', placeholder: '/webhook/my-agent' },
    { name: 'method', label: 'Method', type: 'select', options: ['POST', 'GET', 'PUT'] },
    { name: 'secret', label: 'Secret', type: 'password' },
  ],
};

const ACTION_SCHEMAS: Record<string, ConfigField[]> = {
  summarize: [
    { name: 'style', label: 'Style', type: 'select', options: ['brief', 'detailed', 'bullet_points'] },
    { name: 'max_length', label: 'Max length', type: 'number', placeholder: '500' },
    { name: 'include_key_points', label: 'Include key points', type: 'boolean' },
  ],
  send_message: [
    { name: 'channel', label: 'Channel', type: 'string', placeholder: '#channel-name', required: true },
    { name: 'message_template', label: 'Message template', type: 'textarea', placeholder: 'Use {{summary}} for generated content' },
    { name: 'mention_users', label: 'Mention users', type: 'array', placeholder: '@user' },
  ],
  send_email: [
    { name: 'to', label: 'To', type: 'string', placeholder: 'email@example.com', required: true },
    { name: 'cc', label: 'CC', type: 'string', placeholder: 'Optional CC recipients' },
    { name: 'subject_template', label: 'Subject', type: 'string', placeholder: 'Re: {{original_subject}}' },
    { name: 'body_template', label: 'Body', type: 'textarea', placeholder: 'Email body template...' },
  ],
  create_ticket: [
    { name: 'project', label: 'Project', type: 'string', required: true },
    { name: 'issue_type', label: 'Issue type', type: 'select', options: ['task', 'bug', 'story', 'epic'] },
    { name: 'title_template', label: 'Title', type: 'string', placeholder: '{{title}}' },
    { name: 'description_template', label: 'Description', type: 'textarea' },
    { name: 'priority', label: 'Priority', type: 'select', options: ['low', 'medium', 'high', 'critical'] },
  ],
  filter: [
    { name: 'expression', label: 'Filter expression', type: 'code', placeholder: 'confidence > 0.8' },
    { name: 'on_match', label: 'On match', type: 'select', options: ['continue', 'skip'] },
  ],
  transform: [
    { name: 'expression', label: 'Transform expression', type: 'code', placeholder: '{ ...input, processed: true }' },
    { name: 'output_key', label: 'Output key', type: 'string', placeholder: 'transformed_data' },
  ],
};

interface ConfigField {
  name: string;
  label: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'multiselect' | 'array' | 'textarea' | 'time' | 'password' | 'code';
  placeholder?: string;
  options?: string[];
  required?: boolean;
}

export function AgentEditor({ nodeId, nodeType, onClose }: AgentEditorProps) {
  const {
    trigger,
    actions,
    conditions,
    setTrigger,
    updateAction,
    updateCondition,
  } = useAgentBuilderStore();

  // Get current node data
  const nodeData = useMemo(() => {
    if (nodeType === 'trigger' && trigger?.id === nodeId) {
      return trigger;
    }
    if (nodeType === 'action') {
      return actions.find((a) => a.id === nodeId);
    }
    if (nodeType === 'condition') {
      return conditions.find((c) => c.id === nodeId);
    }
    return null;
  }, [nodeId, nodeType, trigger, actions, conditions]);

  const [config, setConfig] = useState<Record<string, unknown>>(
    (nodeData as TriggerDefinition | ActionDefinition)?.config || {}
  );
  const [name, setName] = useState(
    nodeType === 'condition'
      ? (nodeData as ConditionDefinition)?.description || ''
      : (nodeData as TriggerDefinition | ActionDefinition)?.name || ''
  );
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Get schema for current node type
  const schema = useMemo(() => {
    if (nodeType === 'trigger' && trigger) {
      return TRIGGER_SCHEMAS[trigger.type] || [];
    }
    if (nodeType === 'action') {
      const action = actions.find((a) => a.id === nodeId);
      return action ? ACTION_SCHEMAS[action.type] || [] : [];
    }
    return [];
  }, [nodeType, nodeId, trigger, actions]);

  const handleSave = useCallback(() => {
    // Validate required fields
    const newErrors: Record<string, string> = {};
    schema.forEach((field) => {
      if (field.required && !config[field.name]) {
        newErrors[field.name] = `${field.label} is required`;
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    if (nodeType === 'trigger' && trigger) {
      setTrigger({ ...trigger, name, config });
    } else if (nodeType === 'action') {
      updateAction(nodeId, { name, config });
    } else if (nodeType === 'condition') {
      updateCondition(nodeId, { description: name, expression: name });
    }

    onClose();
  }, [nodeType, nodeId, name, config, schema, trigger, setTrigger, updateAction, updateCondition, onClose]);

  const updateConfig = useCallback((fieldName: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [fieldName]: value }));
    setErrors((prev) => {
      const { [fieldName]: _, ...rest } = prev;
      return rest;
    });
  }, []);

  if (!nodeData) {
    return null;
  }

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-500">{nodeType}</p>
          <h3 className="font-semibold text-gray-900">Edit Configuration</h3>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Name field */}
        <div>
          <label htmlFor="node-name" className="block text-sm font-medium text-gray-700 mb-1">
            Name
          </label>
          <Input
            id="node-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter a name..."
          />
        </div>

        {/* Condition-specific: Expression */}
        {nodeType === 'condition' && (
          <div>
            <label htmlFor="condition-expression" className="block text-sm font-medium text-gray-700 mb-1">
              Expression
            </label>
            <textarea
              id="condition-expression"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., confidence > 0.8"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              rows={3}
            />
            <p className="mt-1 text-xs text-gray-500">
              Use variables like <code>confidence</code>, <code>sender</code>, <code>subject</code>
            </p>
          </div>
        )}

        {/* Dynamic schema fields */}
        {schema.map((field) => (
          <ConfigFieldInput
            key={field.name}
            field={field}
            value={config[field.name]}
            onChange={(value) => updateConfig(field.name, value)}
            error={errors[field.name]}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center gap-2 p-4 border-t border-gray-200">
        <Button variant="outline" onClick={onClose} className="flex-1">
          Cancel
        </Button>
        <Button onClick={handleSave} className="flex-1">
          <Save className="w-4 h-4 mr-2" />
          Save
        </Button>
      </div>
    </div>
  );
}

interface ConfigFieldInputProps {
  field: ConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
  error?: string;
}

function ConfigFieldInput({ field, value, onChange, error }: ConfigFieldInputProps) {
  const [arrayValue, setArrayValue] = useState('');
  const fieldId = `field-${field.name}`;

  return (
    <div>
      <label htmlFor={fieldId} className="block text-sm font-medium text-gray-700 mb-1">
        {field.label}
        {field.required && <span className="text-red-500 ml-1">*</span>}
      </label>

      {field.type === 'string' && (
        <Input
          id={fieldId}
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className={error ? 'border-red-500' : ''}
        />
      )}

      {field.type === 'password' && (
        <Input
          id={fieldId}
          type="password"
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className={error ? 'border-red-500' : ''}
        />
      )}

      {field.type === 'number' && (
        <Input
          id={fieldId}
          type="number"
          value={(value as number) || ''}
          onChange={(e) => onChange(Number(e.target.value))}
          placeholder={field.placeholder}
          className={error ? 'border-red-500' : ''}
        />
      )}

      {field.type === 'time' && (
        <Input
          id={fieldId}
          type="time"
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          className={error ? 'border-red-500' : ''}
        />
      )}

      {field.type === 'boolean' && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            id={fieldId}
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          <span className="text-sm text-gray-600">Enabled</span>
        </label>
      )}

      {field.type === 'select' && (
        <select
          id={fieldId}
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
            error ? 'border-red-500' : 'border-gray-300'
          }`}
        >
          <option value="">Select...</option>
          {field.options?.map((opt) => (
            <option key={opt} value={opt}>
              {opt.charAt(0).toUpperCase() + opt.slice(1).replace('_', ' ')}
            </option>
          ))}
        </select>
      )}

      {field.type === 'multiselect' && (
        <div className="flex flex-wrap gap-2">
          {field.options?.map((opt) => {
            const selected = Array.isArray(value) && value.includes(opt);
            return (
              <button
                key={opt}
                onClick={() => {
                  const current = Array.isArray(value) ? value : [];
                  if (selected) {
                    onChange(current.filter((v: string) => v !== opt));
                  } else {
                    onChange([...current, opt]);
                  }
                }}
                className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                  selected
                    ? 'bg-primary-100 border-primary-500 text-primary-700'
                    : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                {opt}
              </button>
            );
          })}
        </div>
      )}

      {field.type === 'array' && (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {Array.isArray(value) &&
              value.map((item: string, index: number) => (
                <span
                  key={index}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-sm"
                >
                  {item}
                  <button
                    onClick={() => {
                      const current = value as string[];
                      onChange(current.filter((_, i) => i !== index));
                    }}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
          </div>
          <div className="flex gap-2">
            <Input
              value={arrayValue}
              onChange={(e) => setArrayValue(e.target.value)}
              placeholder={field.placeholder}
              className="flex-1"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && arrayValue.trim()) {
                  const current = Array.isArray(value) ? value : [];
                  onChange([...current, arrayValue.trim()]);
                  setArrayValue('');
                }
              }}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (arrayValue.trim()) {
                  const current = Array.isArray(value) ? value : [];
                  onChange([...current, arrayValue.trim()]);
                  setArrayValue('');
                }
              }}
            >
              <Plus className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {(field.type === 'textarea' || field.type === 'code') && (
        <textarea
          id={fieldId}
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className={`w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
            field.type === 'code' ? 'font-mono bg-gray-50' : ''
          } ${error ? 'border-red-500' : 'border-gray-300'}`}
          rows={4}
        />
      )}

      {error && (
        <p className="mt-1 text-xs text-red-500 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {error}
        </p>
      )}
    </div>
  );
}

export default AgentEditor;
