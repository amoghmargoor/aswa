import { useState, useCallback, useEffect, useRef } from 'react';
import {
  Copy,
  Download,
  Upload,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Info,
  Code,
} from 'lucide-react';
import { Button } from '@/components/ui';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';
import { useValidateYaml } from '@/hooks/useAgentGeneration';

interface YAMLEditorProps {
  readOnly?: boolean;
  onSyncToVisual?: () => void;
}

export function YAMLEditor({ readOnly = false, onSyncToVisual }: YAMLEditorProps) {
  const {
    yamlContent,
    yamlErrors,
    agentDefinition,
    trigger,
    actions,
    conditions,
    setYamlContent,
    setYamlErrors,
    syncFromYaml,
  } = useAgentBuilderStore();

  const [localContent, setLocalContent] = useState(yamlContent);
  const [hasChanges, setHasChanges] = useState(false);
  const [copied, setCopied] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const validateYamlMutation = useValidateYaml();

  // Sync local content when store content changes
  useEffect(() => {
    setLocalContent(yamlContent);
    setHasChanges(false);
  }, [yamlContent]);

  // Generate YAML from current state if none exists
  useEffect(() => {
    if (!yamlContent && (trigger || actions.length > 0)) {
      const generated = generateYamlFromState();
      setYamlContent(generated);
    }
  }, [trigger, actions, conditions, yamlContent, setYamlContent]);

  const generateYamlFromState = useCallback(() => {
    const lines: string[] = [];

    // Header
    lines.push('# Agent Definition');
    lines.push(`# Generated at: ${new Date().toISOString()}`);
    lines.push('');

    // Name
    if (agentDefinition?.name) {
      lines.push(`name: ${agentDefinition.name}`);
      lines.push(`display_name: "${agentDefinition.displayName}"`);
      lines.push('');
    }

    // Trigger
    if (trigger) {
      lines.push('trigger:');
      lines.push(`  type: ${trigger.type}`);
      lines.push(`  name: "${trigger.name}"`);
      if (Object.keys(trigger.config).length > 0) {
        lines.push('  config:');
        Object.entries(trigger.config).forEach(([key, value]) => {
          lines.push(`    ${key}: ${formatYamlValue(value)}`);
        });
      }
      lines.push('');
    }

    // Conditions
    if (conditions.length > 0) {
      lines.push('conditions:');
      conditions.forEach((condition) => {
        lines.push(`  - expression: "${condition.expression}"`);
        lines.push(`    description: "${condition.description}"`);
      });
      lines.push('');
    }

    // Actions
    if (actions.length > 0) {
      lines.push('actions:');
      actions.forEach((action) => {
        lines.push(`  - id: ${action.id}`);
        lines.push(`    type: ${action.type}`);
        lines.push(`    name: "${action.name}"`);
        if (action.dependsOn.length > 0) {
          lines.push(`    depends_on: [${action.dependsOn.join(', ')}]`);
        }
        if (Object.keys(action.config).length > 0) {
          lines.push('    config:');
          Object.entries(action.config).forEach(([key, value]) => {
            lines.push(`      ${key}: ${formatYamlValue(value)}`);
          });
        }
      });
      lines.push('');
    }

    // Approval settings
    lines.push('approval:');
    lines.push('  mode: manual');
    lines.push('  timeout_hours: 24');

    return lines.join('\n');
  }, [trigger, actions, conditions, agentDefinition]);

  const formatYamlValue = (value: unknown): string => {
    if (typeof value === 'string') {
      return value.includes('\n') || value.includes(':') || value.includes('#')
        ? `"${value.replace(/"/g, '\\"')}"`
        : value;
    }
    if (Array.isArray(value)) {
      return `[${value.map((v) => formatYamlValue(v)).join(', ')}]`;
    }
    if (typeof value === 'object' && value !== null) {
      return JSON.stringify(value);
    }
    return String(value);
  };

  const handleContentChange = useCallback((content: string) => {
    setLocalContent(content);
    setHasChanges(content !== yamlContent);
    setYamlErrors([]);
  }, [yamlContent]);

  const handleValidate = useCallback(async () => {
    try {
      const result = await validateYamlMutation.mutateAsync(localContent);
      if (result.valid) {
        setYamlErrors([]);
      } else {
        setYamlErrors(result.errors);
      }
    } catch (error) {
      setYamlErrors(['Failed to validate YAML']);
    }
  }, [localContent, validateYamlMutation]);

  const handleApply = useCallback(() => {
    setYamlContent(localContent);
    syncFromYaml();
    setHasChanges(false);
    onSyncToVisual?.();
  }, [localContent, setYamlContent, syncFromYaml, onSyncToVisual]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(localContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  }, [localContent]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([localContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${agentDefinition?.name || 'agent'}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  }, [localContent, agentDefinition]);

  const handleUpload = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.yaml,.yml';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        const content = await file.text();
        handleContentChange(content);
      }
    };
    input.click();
  }, [handleContentChange]);

  const handleRegenerateFromVisual = useCallback(() => {
    const generated = generateYamlFromState();
    handleContentChange(generated);
  }, [generateYamlFromState, handleContentChange]);

  // Line numbers
  const lineNumbers = localContent.split('\n').length;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-2 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-1">
          <Code className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">YAML Editor</span>
        </div>

        <div className="flex-1" />

        {!readOnly && (
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRegenerateFromVisual}
              title="Regenerate from visual builder"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleUpload}
              title="Upload YAML"
            >
              <Upload className="w-4 h-4" />
            </Button>
          </>
        )}

        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          title="Copy to clipboard"
        >
          {copied ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <Copy className="w-4 h-4" />
          )}
        </Button>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleDownload}
          title="Download YAML"
        >
          <Download className="w-4 h-4" />
        </Button>

        {!readOnly && hasChanges && (
          <>
            <div className="w-px h-4 bg-gray-300" />
            <Button variant="outline" size="sm" onClick={handleValidate}>
              Validate
            </Button>
            <Button size="sm" onClick={handleApply}>
              Apply Changes
            </Button>
          </>
        )}
      </div>

      {/* Validation status */}
      {yamlErrors.length > 0 && (
        <div className="px-3 py-2 bg-red-50 border-b border-red-200">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-red-700">
              <p className="font-medium">Validation errors:</p>
              <ul className="list-disc list-inside mt-1">
                {yamlErrors.map((error, index) => (
                  <li key={index}>{error}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {validateYamlMutation.isSuccess && yamlErrors.length === 0 && (
        <div className="px-3 py-2 bg-green-50 border-b border-green-200">
          <div className="flex items-center gap-2 text-sm text-green-700">
            <CheckCircle className="w-4 h-4" />
            YAML is valid
          </div>
        </div>
      )}

      {/* Editor */}
      <div className="flex-1 flex overflow-hidden">
        {/* Line numbers */}
        <div className="py-3 px-2 bg-gray-100 border-r border-gray-200 text-right select-none overflow-hidden">
          {Array.from({ length: lineNumbers }, (_, i) => (
            <div key={i} className="text-xs text-gray-400 font-mono leading-5">
              {i + 1}
            </div>
          ))}
        </div>

        {/* Content */}
        <textarea
          ref={textareaRef}
          value={localContent}
          onChange={(e) => handleContentChange(e.target.value)}
          readOnly={readOnly}
          className={`flex-1 p-3 font-mono text-sm leading-5 resize-none focus:outline-none ${
            readOnly ? 'bg-gray-50 text-gray-600' : 'bg-white text-gray-900'
          }`}
          placeholder="# Agent YAML definition..."
          spellCheck={false}
        />
      </div>

      {/* Footer */}
      <div className="flex items-center gap-4 px-3 py-2 border-t border-gray-200 bg-gray-50 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <Info className="w-3 h-3" />
          <span>{lineNumbers} lines</span>
        </div>
        <div>{localContent.length} characters</div>
        {hasChanges && (
          <div className="flex items-center gap-1 text-amber-600">
            <AlertCircle className="w-3 h-3" />
            Unsaved changes
          </div>
        )}
      </div>
    </div>
  );
}

export default YAMLEditor;
