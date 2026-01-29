# Task 9.3.5: YAML Editor

## Objective

Implement a YAML-based code editor for power users who prefer direct YAML editing with syntax highlighting, validation, and auto-completion.

## Prerequisites

- Task 9.3.1-9.3.4 completed
- Monaco Editor or CodeMirror integration

## Implementation

### Step 1: YAML Editor Component

```tsx
// services/web-dashboard/src/components/agents/YAMLEditor.tsx
import React, { useCallback, useRef, useState } from 'react';
import Editor, { Monaco, OnMount } from '@monaco-editor/react';
import { editor } from 'monaco-editor';
import yaml from 'js-yaml';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  DocumentDuplicateIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
} from '@heroicons/react/24/outline';

import { agentDefinitionSchema } from '../../schemas/agentDefinition';
import { useValidateDefinition } from '../../hooks/useAgentGeneration';

interface Props {
  initialValue?: string;
  onChange?: (value: string, isValid: boolean) => void;
  onSave?: (definition: object) => void;
  readOnly?: boolean;
}

const DEFAULT_YAML = `# Agent Definition
name: my-agent
displayName: My Agent
description: Describe what this agent does

trigger:
  type: email
  config:
    subject_filter: ""

actions:
  - id: action_1
    type: summarize
    config:
      max_length: 500

approval:
  mode: review
  timeout_hours: 24
`;

export function YAMLEditor({ initialValue, onChange, onSave, readOnly = false }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const [yamlValue, setYamlValue] = useState(initialValue || DEFAULT_YAML);
  const [errors, setErrors] = useState<string[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [isValid, setIsValid] = useState(true);

  const validateDefinition = useValidateDefinition();

  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Configure YAML language
    configureYAMLLanguage(monaco);

    // Register agent definition schema
    registerAgentSchema(monaco);

    // Add custom keybindings
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      handleSave();
    });

    // Initial validation
    validateContent(yamlValue);
  };

  const configureYAMLLanguage = (monaco: Monaco) => {
    // Register YAML language if not already registered
    if (!monaco.languages.getLanguages().some((l) => l.id === 'yaml')) {
      monaco.languages.register({ id: 'yaml' });
    }

    // Configure YAML tokens
    monaco.languages.setMonarchTokensProvider('yaml', {
      tokenizer: {
        root: [
          [/^[\t ]*#.*$/, 'comment'],
          [/^[\t ]*[a-zA-Z_][\w]*(?=\s*:)/, 'key'],
          [/:/, 'delimiter'],
          [/".*?"/, 'string'],
          [/'.*?'/, 'string'],
          [/\d+/, 'number'],
          [/true|false|null/, 'keyword'],
          [/-/, 'delimiter'],
        ],
      },
    });
  };

  const registerAgentSchema = (monaco: Monaco) => {
    // Register completion provider
    monaco.languages.registerCompletionItemProvider('yaml', {
      provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        const suggestions = getCompletionSuggestions(model, position, range);
        return { suggestions };
      },
    });

    // Register hover provider
    monaco.languages.registerHoverProvider('yaml', {
      provideHover: (model, position) => {
        const word = model.getWordAtPosition(position);
        if (!word) return null;

        const hoverContent = getHoverContent(word.word);
        if (!hoverContent) return null;

        return {
          contents: [{ value: hoverContent }],
        };
      },
    });
  };

  const getCompletionSuggestions = (
    model: editor.ITextModel,
    position: any,
    range: any
  ) => {
    const lineContent = model.getLineContent(position.lineNumber);
    const indentLevel = lineContent.search(/\S|$/);

    // Root level completions
    if (indentLevel === 0) {
      return [
        {
          label: 'name',
          kind: 10, // Property
          insertText: 'name: ${1:my-agent}',
          insertTextRules: 4,
          documentation: 'Unique agent identifier (lowercase, hyphens allowed)',
          range,
        },
        {
          label: 'displayName',
          kind: 10,
          insertText: 'displayName: ${1:My Agent}',
          insertTextRules: 4,
          documentation: 'Human-readable agent name',
          range,
        },
        {
          label: 'trigger',
          kind: 10,
          insertText: 'trigger:\n  type: ${1|email,slack,schedule,webhook,document|}\n  config:\n    $0',
          insertTextRules: 4,
          documentation: 'Defines when the agent should run',
          range,
        },
        {
          label: 'actions',
          kind: 10,
          insertText: 'actions:\n  - id: ${1:action_1}\n    type: ${2|summarize,extract,send_slack,send_email,create_ticket|}\n    config:\n      $0',
          insertTextRules: 4,
          documentation: 'List of actions to perform',
          range,
        },
        {
          label: 'approval',
          kind: 10,
          insertText: 'approval:\n  mode: ${1|auto,notify,review,manual|}\n  timeout_hours: ${2:24}',
          insertTextRules: 4,
          documentation: 'Approval settings for agent actions',
          range,
        },
      ];
    }

    // Trigger type completions
    if (lineContent.includes('type:') && lineContent.trim().startsWith('type:')) {
      return [
        { label: 'email', kind: 12, insertText: 'email', documentation: 'Trigger on email receipt', range },
        { label: 'slack', kind: 12, insertText: 'slack', documentation: 'Trigger on Slack message', range },
        { label: 'schedule', kind: 12, insertText: 'schedule', documentation: 'Trigger on schedule', range },
        { label: 'webhook', kind: 12, insertText: 'webhook', documentation: 'Trigger via webhook', range },
        { label: 'document', kind: 12, insertText: 'document', documentation: 'Trigger on document upload', range },
      ];
    }

    // Action type completions
    if (lineContent.includes('type:') && indentLevel >= 4) {
      return [
        { label: 'summarize', kind: 12, insertText: 'summarize', documentation: 'Generate content summary', range },
        { label: 'extract', kind: 12, insertText: 'extract', documentation: 'Extract specific data', range },
        { label: 'send_slack', kind: 12, insertText: 'send_slack', documentation: 'Send Slack message', range },
        { label: 'send_email', kind: 12, insertText: 'send_email', documentation: 'Send email', range },
        { label: 'create_ticket', kind: 12, insertText: 'create_ticket', documentation: 'Create issue ticket', range },
        { label: 'query_knowledge', kind: 12, insertText: 'query_knowledge', documentation: 'Query knowledge base', range },
        { label: 'transform', kind: 12, insertText: 'transform', documentation: 'Transform data', range },
      ];
    }

    return [];
  };

  const getHoverContent = (word: string): string | null => {
    const docs: Record<string, string> = {
      name: '**name** (string)\n\nUnique identifier for the agent. Use lowercase letters, numbers, and hyphens.',
      displayName: '**displayName** (string)\n\nHuman-readable name shown in the UI.',
      description: '**description** (string)\n\nDetailed description of what the agent does.',
      trigger: '**trigger** (object)\n\nDefines the event that starts the agent.\n\nRequired properties:\n- `type`: Trigger type (email, slack, schedule, webhook, document)\n- `config`: Trigger-specific configuration',
      actions: '**actions** (array)\n\nList of actions the agent performs.\n\nEach action requires:\n- `id`: Unique action identifier\n- `type`: Action type\n- `config`: Action configuration',
      approval: '**approval** (object)\n\nHow agent actions should be approved.\n\nModes:\n- `auto`: Execute automatically\n- `notify`: Execute and notify\n- `review`: Require review before execution\n- `manual`: Always require manual approval',
    };

    return docs[word] || null;
  };

  const validateContent = useCallback(async (content: string) => {
    const newErrors: string[] = [];
    const newWarnings: string[] = [];

    try {
      // Parse YAML
      const parsed = yaml.load(content);

      if (typeof parsed !== 'object' || parsed === null) {
        newErrors.push('Invalid YAML: Must be an object');
      } else {
        // Validate against schema
        const result = agentDefinitionSchema.safeParse(parsed);

        if (!result.success) {
          for (const issue of result.error.issues) {
            const path = issue.path.join('.');
            newErrors.push(`${path}: ${issue.message}`);
          }
        }

        // Backend validation
        try {
          const response = await validateDefinition.mutateAsync(parsed);
          if (response.warnings) {
            newWarnings.push(...response.warnings);
          }
        } catch {
          // Ignore backend validation errors during typing
        }
      }
    } catch (e) {
      if (e instanceof yaml.YAMLException) {
        newErrors.push(`YAML syntax error at line ${e.mark?.line || '?'}: ${e.message}`);
      } else {
        newErrors.push(`Parse error: ${String(e)}`);
      }
    }

    setErrors(newErrors);
    setWarnings(newWarnings);
    setIsValid(newErrors.length === 0);

    // Update markers in editor
    if (monacoRef.current && editorRef.current) {
      const model = editorRef.current.getModel();
      if (model) {
        const markers = newErrors.map((error, index) => ({
          severity: monacoRef.current!.MarkerSeverity.Error,
          message: error,
          startLineNumber: 1,
          startColumn: 1,
          endLineNumber: 1,
          endColumn: 1,
        }));

        monacoRef.current.editor.setModelMarkers(model, 'yaml-validator', markers);
      }
    }
  }, [validateDefinition]);

  const handleEditorChange = useCallback((value: string | undefined) => {
    const newValue = value || '';
    setYamlValue(newValue);
    validateContent(newValue);
    onChange?.(newValue, errors.length === 0);
  }, [onChange, errors.length, validateContent]);

  const handleSave = useCallback(() => {
    if (!isValid) return;

    try {
      const parsed = yaml.load(yamlValue);
      onSave?.(parsed as object);
    } catch {
      // Already handled in validation
    }
  }, [yamlValue, isValid, onSave]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(yamlValue);
  }, [yamlValue]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([yamlValue], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'agent-definition.yaml';
    a.click();
    URL.revokeObjectURL(url);
  }, [yamlValue]);

  const handleUpload = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.yaml,.yml';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        const content = await file.text();
        setYamlValue(content);
        handleEditorChange(content);
      }
    };
    input.click();
  }, [handleEditorChange]);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-100 border-b">
        <div className="flex items-center space-x-2">
          {isValid ? (
            <span className="flex items-center text-sm text-green-600">
              <CheckCircleIcon className="w-4 h-4 mr-1" />
              Valid
            </span>
          ) : (
            <span className="flex items-center text-sm text-red-600">
              <ExclamationTriangleIcon className="w-4 h-4 mr-1" />
              {errors.length} error{errors.length !== 1 ? 's' : ''}
            </span>
          )}
          {warnings.length > 0 && (
            <span className="flex items-center text-sm text-yellow-600">
              <ExclamationTriangleIcon className="w-4 h-4 mr-1" />
              {warnings.length} warning{warnings.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleUpload}
            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
            title="Upload YAML"
          >
            <ArrowUpTrayIcon className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownload}
            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
            title="Download YAML"
          >
            <ArrowDownTrayIcon className="w-4 h-4" />
          </button>
          <button
            onClick={handleCopy}
            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
            title="Copy to clipboard"
          >
            <DocumentDuplicateIcon className="w-4 h-4" />
          </button>
          {!readOnly && (
            <button
              onClick={handleSave}
              disabled={!isValid}
              className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save
            </button>
          )}
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1">
        <Editor
          height="100%"
          language="yaml"
          value={yamlValue}
          onChange={handleEditorChange}
          onMount={handleEditorMount}
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            wordWrap: 'on',
            folding: true,
            renderLineHighlight: 'all',
            suggestOnTriggerCharacters: true,
            quickSuggestions: true,
          }}
          theme="vs-light"
        />
      </div>

      {/* Errors Panel */}
      {(errors.length > 0 || warnings.length > 0) && (
        <div className="max-h-32 overflow-y-auto border-t bg-gray-50">
          {errors.map((error, index) => (
            <div key={`error-${index}`} className="flex items-start px-4 py-2 text-sm text-red-700 border-b border-red-100">
              <ExclamationTriangleIcon className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" />
              {error}
            </div>
          ))}
          {warnings.map((warning, index) => (
            <div key={`warning-${index}`} className="flex items-start px-4 py-2 text-sm text-yellow-700 border-b border-yellow-100">
              <ExclamationTriangleIcon className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" />
              {warning}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Step 2: Agent Definition Schema

```typescript
// services/web-dashboard/src/schemas/agentDefinition.ts
import { z } from 'zod';

// Trigger schemas
const emailTriggerConfig = z.object({
  subject_filter: z.string().optional(),
  sender_filter: z.string().optional(),
  has_attachment: z.boolean().optional(),
});

const slackTriggerConfig = z.object({
  channel: z.string().optional(),
  mentions_bot: z.boolean().optional(),
  keyword_filter: z.string().optional(),
});

const scheduleTriggerConfig = z.object({
  cron: z.string(),
  timezone: z.string().optional(),
});

const webhookTriggerConfig = z.object({
  path: z.string().optional(),
  method: z.enum(['GET', 'POST', 'PUT']).optional(),
  secret: z.string().optional(),
});

const documentTriggerConfig = z.object({
  source: z.string().optional(),
  file_types: z.array(z.string()).optional(),
});

const triggerSchema = z.object({
  type: z.enum(['email', 'slack', 'schedule', 'webhook', 'document']),
  config: z.union([
    emailTriggerConfig,
    slackTriggerConfig,
    scheduleTriggerConfig,
    webhookTriggerConfig,
    documentTriggerConfig,
    z.record(z.unknown()),
  ]).optional(),
});

// Action schemas
const summarizeConfig = z.object({
  max_length: z.number().min(50).max(5000).optional(),
  style: z.enum(['brief', 'detailed', 'bullet_points']).optional(),
  focus_on: z.string().optional(),
});

const extractConfig = z.object({
  extract_type: z.enum(['action_items', 'entities', 'key_points', 'custom']).optional(),
  schema: z.record(z.unknown()).optional(),
});

const sendSlackConfig = z.object({
  channel: z.string(),
  message_template: z.string().optional(),
  include_source: z.boolean().optional(),
});

const sendEmailConfig = z.object({
  to: z.union([z.string(), z.array(z.string())]),
  subject_template: z.string().optional(),
  body_template: z.string().optional(),
});

const createTicketConfig = z.object({
  project: z.string(),
  issue_type: z.string().optional(),
  title_template: z.string().optional(),
  description_template: z.string().optional(),
  priority: z.enum(['low', 'medium', 'high', 'critical']).optional(),
  labels: z.array(z.string()).optional(),
});

const actionSchema = z.object({
  id: z.string().min(1),
  type: z.enum([
    'summarize',
    'extract',
    'send_slack',
    'send_email',
    'create_ticket',
    'query_knowledge',
    'transform',
    'condition',
    'http_request',
  ]),
  config: z.union([
    summarizeConfig,
    extractConfig,
    sendSlackConfig,
    sendEmailConfig,
    createTicketConfig,
    z.record(z.unknown()),
  ]).optional(),
  description: z.string().optional(),
  depends_on: z.array(z.string()).optional(),
  condition: z.string().optional(),
});

// Condition schema
const conditionSchema = z.object({
  id: z.string().optional(),
  expression: z.string(),
  description: z.string().optional(),
});

// Approval schema
const approvalSchema = z.object({
  mode: z.enum(['auto', 'notify', 'review', 'manual']),
  timeout_hours: z.number().min(1).max(168).optional(),
  approvers: z.array(z.string()).optional(),
  escalation_after_hours: z.number().optional(),
  confidence_threshold: z.number().min(0).max(1).optional(),
});

// Main agent definition schema
export const agentDefinitionSchema = z.object({
  name: z.string()
    .min(3, 'Name must be at least 3 characters')
    .max(50, 'Name must be at most 50 characters')
    .regex(/^[a-z0-9-]+$/, 'Name must be lowercase with hyphens only'),
  displayName: z.string()
    .min(3, 'Display name must be at least 3 characters')
    .max(100, 'Display name must be at most 100 characters'),
  description: z.string().max(500).optional(),
  version: z.string().optional(),
  enabled: z.boolean().optional(),
  trigger: triggerSchema,
  conditions: z.array(conditionSchema).optional(),
  actions: z.array(actionSchema).min(1, 'At least one action is required'),
  approval: approvalSchema.optional(),
  metadata: z.record(z.unknown()).optional(),
  tags: z.array(z.string()).optional(),
});

export type AgentDefinition = z.infer<typeof agentDefinitionSchema>;
export type TriggerConfig = z.infer<typeof triggerSchema>;
export type ActionConfig = z.infer<typeof actionSchema>;
export type ApprovalConfig = z.infer<typeof approvalSchema>;
```

### Step 3: YAML Editor Page Integration

```tsx
// services/web-dashboard/src/pages/agents/[id]/edit.tsx
import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tab } from '@headlessui/react';
import yaml from 'js-yaml';

import { apiClient } from '../../../lib/apiClient';
import { FormBuilder } from '../../../components/agents/FormBuilder';
import { VisualFlowBuilder } from '../../../components/agents/VisualFlowBuilder';
import { YAMLEditor } from '../../../components/agents/YAMLEditor';

type EditorMode = 'form' | 'visual' | 'yaml';

export function AgentEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeMode, setActiveMode] = useState<EditorMode>('form');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const { data: agent, isLoading } = useQuery({
    queryKey: ['agent', id],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/agents/${id}`);
      return response.data;
    },
  });

  const updateAgent = useMutation({
    mutationFn: async (definition: object) => {
      await apiClient.put(`/api/v1/agents/${id}`, { definition });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent', id] });
      setHasUnsavedChanges(false);
    },
  });

  const handleSave = (definition: object) => {
    updateAgent.mutate(definition);
  };

  const handleModeChange = (mode: EditorMode) => {
    if (hasUnsavedChanges) {
      if (!confirm('You have unsaved changes. Switch anyway?')) {
        return;
      }
    }
    setActiveMode(mode);
  };

  if (isLoading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  if (!agent) {
    return <div className="text-center py-12">Agent not found</div>;
  }

  const yamlContent = yaml.dump(agent.definition);

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b">
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            Edit: {agent.displayName}
          </h1>
          <p className="text-sm text-gray-500">{agent.name}</p>
        </div>

        <div className="flex items-center space-x-4">
          {hasUnsavedChanges && (
            <span className="text-sm text-yellow-600">Unsaved changes</span>
          )}
          <button
            onClick={() => navigate(`/agents/${id}`)}
            className="px-4 py-2 text-gray-600 hover:text-gray-900"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* Mode Tabs */}
      <div className="px-6 pt-4 bg-white border-b">
        <Tab.Group
          selectedIndex={['form', 'visual', 'yaml'].indexOf(activeMode)}
          onChange={(index) => handleModeChange(['form', 'visual', 'yaml'][index] as EditorMode)}
        >
          <Tab.List className="flex space-x-4">
            <Tab className={({ selected }) => `
              px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors
              ${selected
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
              }
            `}>
              Form Builder
            </Tab>
            <Tab className={({ selected }) => `
              px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors
              ${selected
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
              }
            `}>
              Visual Flow
            </Tab>
            <Tab className={({ selected }) => `
              px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors
              ${selected
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
              }
            `}>
              YAML Editor
            </Tab>
          </Tab.List>
        </Tab.Group>
      </div>

      {/* Editor Content */}
      <div className="flex-1 overflow-hidden">
        {activeMode === 'form' && (
          <div className="h-full overflow-y-auto p-6">
            <FormBuilder
              initialData={agent.definition}
              onSave={handleSave}
              onChange={() => setHasUnsavedChanges(true)}
            />
          </div>
        )}

        {activeMode === 'visual' && (
          <VisualFlowBuilder
            initialDefinition={agent.definition}
            onSave={handleSave}
            onChange={() => setHasUnsavedChanges(true)}
          />
        )}

        {activeMode === 'yaml' && (
          <YAMLEditor
            initialValue={yamlContent}
            onSave={handleSave}
            onChange={(_, isValid) => {
              if (isValid) setHasUnsavedChanges(true);
            }}
          />
        )}
      </div>

      {/* Save Status */}
      {updateAgent.isPending && (
        <div className="fixed bottom-4 right-4 px-4 py-2 bg-indigo-600 text-white rounded-lg shadow-lg">
          Saving...
        </div>
      )}

      {updateAgent.isSuccess && (
        <div className="fixed bottom-4 right-4 px-4 py-2 bg-green-600 text-white rounded-lg shadow-lg">
          Saved successfully!
        </div>
      )}

      {updateAgent.isError && (
        <div className="fixed bottom-4 right-4 px-4 py-2 bg-red-600 text-white rounded-lg shadow-lg">
          Failed to save. Please try again.
        </div>
      )}
    </div>
  );
}
```

### Step 4: Validation API Hook

```typescript
// services/web-dashboard/src/hooks/useAgentGeneration.ts (additions)

export function useValidateDefinition() {
  return useMutation({
    mutationFn: async (definition: object): Promise<{
      valid: boolean;
      errors: string[];
      warnings: string[];
    }> => {
      const response = await apiClient.post('/api/v1/agents/validate', {
        definition,
      });
      return response.data;
    },
  });
}

export function useImportYAML() {
  return useMutation({
    mutationFn: async (yamlContent: string): Promise<{
      definition: object;
      warnings: string[];
    }> => {
      const response = await apiClient.post('/api/v1/agents/import', {
        yaml: yamlContent,
      });
      return response.data;
    },
  });
}

export function useExportYAML() {
  return useMutation({
    mutationFn: async (agentId: string): Promise<string> => {
      const response = await apiClient.get(`/api/v1/agents/${agentId}/export`, {
        headers: {
          Accept: 'text/yaml',
        },
      });
      return response.data;
    },
  });
}
```

### Step 5: Backend Validation Endpoint

```python
# services/agent-service/src/aswa_agents/api/validation.py
"""Agent definition validation endpoints."""

from typing import Any

import structlog
import yaml as pyyaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aswa_agents.generation.capability_registry import CapabilityRegistry
from aswa_agents.models.agent_definition import AgentDefinitionModel

logger = structlog.get_logger()
router = APIRouter(prefix="/agents", tags=["validation"])


class ValidateRequest(BaseModel):
    """Request to validate an agent definition."""

    definition: dict[str, Any]


class ValidateResponse(BaseModel):
    """Validation response."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImportRequest(BaseModel):
    """Request to import YAML."""

    yaml: str


class ImportResponse(BaseModel):
    """Import response."""

    definition: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


@router.post("/validate", response_model=ValidateResponse)
async def validate_definition(request: ValidateRequest) -> ValidateResponse:
    """
    Validate an agent definition.

    Performs:
    - Schema validation
    - Capability availability check
    - Configuration validation
    """
    errors = []
    warnings = []

    try:
        # Parse with Pydantic model
        definition = AgentDefinitionModel(**request.definition)

        # Check trigger capability
        trigger_cap = CapabilityRegistry.get_capability(
            f"trigger_{definition.trigger.type}"
        )
        if not trigger_cap:
            warnings.append(
                f"Unknown trigger type: {definition.trigger.type}"
            )

        # Check action capabilities
        for action in definition.actions:
            action_cap = CapabilityRegistry.get_capability(
                f"action_{action.type}"
            )
            if not action_cap:
                warnings.append(f"Unknown action type: {action.type}")

            # Check required parameters
            if action_cap and action_cap.required_parameters:
                for param in action_cap.required_parameters:
                    if param not in (action.config or {}):
                        errors.append(
                            f"Action '{action.id}' missing required parameter: {param}"
                        )

        # Validate action dependencies
        action_ids = {a.id for a in definition.actions}
        for action in definition.actions:
            if action.depends_on:
                for dep in action.depends_on:
                    if dep not in action_ids:
                        errors.append(
                            f"Action '{action.id}' depends on unknown action: {dep}"
                        )

        # Check for circular dependencies
        if _has_circular_dependency(definition.actions):
            errors.append("Circular dependency detected in actions")

    except Exception as e:
        errors.append(f"Validation error: {str(e)}")

    return ValidateResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@router.post("/import", response_model=ImportResponse)
async def import_yaml(request: ImportRequest) -> ImportResponse:
    """Import and parse YAML agent definition."""
    warnings = []

    try:
        definition = pyyaml.safe_load(request.yaml)

        if not isinstance(definition, dict):
            raise HTTPException(
                status_code=400,
                detail="YAML must parse to an object",
            )

        # Basic normalization
        if "displayName" not in definition and "name" in definition:
            definition["displayName"] = definition["name"].replace("-", " ").title()
            warnings.append("displayName auto-generated from name")

        if "approval" not in definition:
            definition["approval"] = {"mode": "review", "timeout_hours": 24}
            warnings.append("Default approval settings added")

        return ImportResponse(
            definition=definition,
            warnings=warnings,
        )

    except pyyaml.YAMLException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML: {str(e)}",
        )


@router.get("/{agent_id}/export")
async def export_yaml(agent_id: str) -> str:
    """Export agent definition as YAML."""
    # In real implementation, fetch from database
    # For now, return placeholder
    from aswa_agents.repositories.agent_repository import AgentRepository

    repo = AgentRepository()
    agent = await repo.get_by_id(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    yaml_content = pyyaml.dump(
        agent.definition,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    return yaml_content


def _has_circular_dependency(actions: list) -> bool:
    """Check for circular dependencies in action graph."""
    # Build dependency graph
    graph: dict[str, set[str]] = {a.id: set(a.depends_on or []) for a in actions}

    # DFS to detect cycles
    visited = set()
    rec_stack = set()

    def has_cycle(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    for node in graph:
        if node not in visited:
            if has_cycle(node):
                return True

    return False
```

## Test Cases

```typescript
// services/web-dashboard/src/components/agents/__tests__/YAMLEditor.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { YAMLEditor } from '../YAMLEditor';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

describe('YAMLEditor', () => {
  it('renders with default content', () => {
    render(<YAMLEditor />, { wrapper });

    expect(screen.getByText('Valid')).toBeInTheDocument();
  });

  it('shows validation errors for invalid YAML', async () => {
    const invalidYaml = `
name: test
trigger: [invalid
`;

    render(<YAMLEditor initialValue={invalidYaml} />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  it('validates required fields', async () => {
    const incompleteYaml = `
name: test-agent
displayName: Test Agent
# Missing trigger and actions
`;

    render(<YAMLEditor initialValue={incompleteYaml} />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  it('calls onSave with parsed definition', async () => {
    const onSave = jest.fn();
    const validYaml = `
name: test-agent
displayName: Test Agent
trigger:
  type: email
actions:
  - id: action_1
    type: summarize
`;

    render(<YAMLEditor initialValue={validYaml} onSave={onSave} />, { wrapper });

    const saveButton = screen.getByText('Save');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'test-agent',
          displayName: 'Test Agent',
        })
      );
    });
  });

  it('handles copy to clipboard', async () => {
    const mockClipboard = {
      writeText: jest.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(<YAMLEditor initialValue="test: content" />, { wrapper });

    const copyButton = screen.getByTitle('Copy to clipboard');
    fireEvent.click(copyButton);

    expect(mockClipboard.writeText).toHaveBeenCalledWith('test: content');
  });

  it('disables save button when invalid', async () => {
    const invalidYaml = 'invalid: [yaml';

    render(<YAMLEditor initialValue={invalidYaml} />, { wrapper });

    await waitFor(() => {
      const saveButton = screen.getByText('Save');
      expect(saveButton).toBeDisabled();
    });
  });
});

describe('agentDefinitionSchema', () => {
  it('validates correct definition', () => {
    const { agentDefinitionSchema } = require('../../schemas/agentDefinition');

    const validDef = {
      name: 'test-agent',
      displayName: 'Test Agent',
      trigger: { type: 'email' },
      actions: [{ id: 'action_1', type: 'summarize' }],
    };

    const result = agentDefinitionSchema.safeParse(validDef);
    expect(result.success).toBe(true);
  });

  it('rejects invalid name format', () => {
    const { agentDefinitionSchema } = require('../../schemas/agentDefinition');

    const invalidDef = {
      name: 'Invalid Name!',
      displayName: 'Test',
      trigger: { type: 'email' },
      actions: [{ id: 'action_1', type: 'summarize' }],
    };

    const result = agentDefinitionSchema.safeParse(invalidDef);
    expect(result.success).toBe(false);
  });

  it('requires at least one action', () => {
    const { agentDefinitionSchema } = require('../../schemas/agentDefinition');

    const invalidDef = {
      name: 'test-agent',
      displayName: 'Test',
      trigger: { type: 'email' },
      actions: [],
    };

    const result = agentDefinitionSchema.safeParse(invalidDef);
    expect(result.success).toBe(false);
  });
});
```

```python
# services/agent-service/tests/unit/test_validation.py
"""Tests for validation endpoints."""

import pytest
from fastapi.testclient import TestClient

from aswa_agents.api.validation import _has_circular_dependency
from aswa_agents.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestValidateEndpoint:
    """Test validation endpoint."""

    def test_valid_definition(self, client):
        """Test validating a correct definition."""
        response = client.post("/api/v1/agents/validate", json={
            "definition": {
                "name": "test-agent",
                "displayName": "Test Agent",
                "trigger": {"type": "email"},
                "actions": [
                    {"id": "action_1", "type": "summarize"}
                ],
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0

    def test_missing_trigger(self, client):
        """Test validation with missing trigger."""
        response = client.post("/api/v1/agents/validate", json={
            "definition": {
                "name": "test-agent",
                "displayName": "Test Agent",
                "actions": [{"id": "action_1", "type": "summarize"}],
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_circular_dependency_detection(self, client):
        """Test circular dependency detection."""
        response = client.post("/api/v1/agents/validate", json={
            "definition": {
                "name": "test-agent",
                "displayName": "Test Agent",
                "trigger": {"type": "email"},
                "actions": [
                    {"id": "a", "type": "summarize", "depends_on": ["b"]},
                    {"id": "b", "type": "extract", "depends_on": ["c"]},
                    {"id": "c", "type": "send_slack", "depends_on": ["a"]},
                ],
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("circular" in e.lower() for e in data["errors"])


class TestImportEndpoint:
    """Test YAML import endpoint."""

    def test_valid_yaml_import(self, client):
        """Test importing valid YAML."""
        yaml_content = """
name: imported-agent
displayName: Imported Agent
trigger:
  type: email
actions:
  - id: action_1
    type: summarize
"""
        response = client.post("/api/v1/agents/import", json={
            "yaml": yaml_content,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["definition"]["name"] == "imported-agent"

    def test_invalid_yaml_syntax(self, client):
        """Test importing invalid YAML."""
        invalid_yaml = """
name: test
trigger: [invalid
"""
        response = client.post("/api/v1/agents/import", json={
            "yaml": invalid_yaml,
        })

        assert response.status_code == 400


class TestCircularDependency:
    """Test circular dependency detection."""

    def test_no_cycle(self):
        """Test graph without cycles."""
        from dataclasses import dataclass

        @dataclass
        class MockAction:
            id: str
            depends_on: list = None

        actions = [
            MockAction(id="a", depends_on=["b"]),
            MockAction(id="b", depends_on=["c"]),
            MockAction(id="c", depends_on=[]),
        ]

        assert _has_circular_dependency(actions) is False

    def test_with_cycle(self):
        """Test graph with cycles."""
        from dataclasses import dataclass

        @dataclass
        class MockAction:
            id: str
            depends_on: list = None

        actions = [
            MockAction(id="a", depends_on=["b"]),
            MockAction(id="b", depends_on=["a"]),
        ]

        assert _has_circular_dependency(actions) is True
```

## Verification Steps

1. **Run component tests:**
   ```bash
   cd services/web-dashboard
   npm test -- --testPathPattern=YAMLEditor
   ```

2. **Run backend tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_validation.py -v
   ```

3. **Test in browser:**
   - Navigate to /agents/new
   - Switch to YAML mode
   - Verify syntax highlighting
   - Test auto-completion with Ctrl+Space
   - Verify validation errors appear

4. **Test import/export:**
   - Create agent via form builder
   - Switch to YAML view
   - Download YAML file
   - Create new agent and upload the file

## Next Task

Proceed to `task-9.4.1-core-action-blocks.md` for implementing core action blocks.
