import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  GitBranch,
  Code,
  Eye,
  Save,
  Play,
  Undo2,
  Redo2,
  HelpCircle,
} from 'lucide-react';
import { Button, Card } from '@/components/ui';
import { NLPBuilder, FlowBuilder, AgentEditor, YAMLEditor } from '@/components/agents';
import { useAgentBuilderStore, BuilderMode, BuilderStep } from '@/stores/agentBuilderStore';
import { useAgent, useCreateAgent, useUpdateAgent } from '@/hooks/useAgentGeneration';

const MODE_TABS = [
  { id: 'nlp' as BuilderMode, label: 'AI Builder', icon: Sparkles },
  { id: 'visual' as BuilderMode, label: 'Visual', icon: GitBranch },
  { id: 'yaml' as BuilderMode, label: 'YAML', icon: Code },
];

const STEP_LABELS: Record<BuilderStep, string> = {
  describe: 'Describe',
  configure: 'Configure',
  review: 'Review',
  deploy: 'Deploy',
};

export default function AgentBuilder() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = !!id && id !== 'new';

  const {
    mode,
    step,
    trigger,
    actions,
    conditions,
    agentDefinition,
    selectedNodeId,
    undoStack,
    redoStack,
    setMode,
    setStep,
    setAgentDefinition,
    setTrigger,
    reset,
    undo,
    redo,
  } = useAgentBuilderStore();

  const [showEditor, setShowEditor] = useState(false);
  const [editorNodeId, setEditorNodeId] = useState<string | null>(null);
  const [editorNodeType, setEditorNodeType] = useState<'trigger' | 'action' | 'condition'>('trigger');

  // Load existing agent if editing
  const { data: existingAgent } = useAgent(isEditing ? id : '');
  const createAgent = useCreateAgent();
  const updateAgent = useUpdateAgent();

  useEffect(() => {
    if (existingAgent) {
      setTrigger(existingAgent.trigger);
      // Load actions and conditions from existing agent
      // This would need the store to have methods to set all actions/conditions at once
    }
  }, [existingAgent]);

  // Reset on unmount
  useEffect(() => {
    return () => {
      reset();
    };
  }, []);

  const handleNodeSelect = useCallback(
    (nodeId: string, nodeType: 'trigger' | 'action' | 'condition') => {
      setEditorNodeId(nodeId);
      setEditorNodeType(nodeType);
      setShowEditor(true);
    },
    []
  );

  const handleSave = useCallback(async () => {
    if (!agentDefinition) return;

    try {
      if (isEditing) {
        await updateAgent.mutateAsync({
          id,
          updates: {
            trigger,
            actions,
            conditions,
          },
        });
      } else {
        await createAgent.mutateAsync(agentDefinition);
      }
      navigate('/agents');
    } catch (error) {
      console.error('Failed to save agent:', error);
    }
  }, [isEditing, id, agentDefinition, trigger, actions, conditions, createAgent, updateAgent, navigate]);

  const handleDeploy = useCallback(async () => {
    // First save, then activate
    await handleSave();
  }, [handleSave]);

  const canSave = trigger && actions.length > 0;
  const canUndo = undoStack.length > 0;
  const canRedo = redoStack.length > 0;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Top Bar */}
      <header className="flex items-center gap-4 px-4 py-3 bg-white border-b border-gray-200">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/agents')}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>

        <div className="flex-1">
          <h1 className="font-semibold text-gray-900">
            {isEditing ? 'Edit Agent' : 'Create New Agent'}
          </h1>
        </div>

        {/* Mode tabs */}
        <div className="flex items-center bg-gray-100 rounded-lg p-1">
          {MODE_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = mode === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setMode(tab.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Undo/Redo */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={undo}
            disabled={!canUndo}
            title="Undo"
          >
            <Undo2 className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={redo}
            disabled={!canRedo}
            title="Redo"
          >
            <Redo2 className="w-4 h-4" />
          </Button>
        </div>

        <div className="w-px h-6 bg-gray-200" />

        {/* Actions */}
        <Button variant="outline" onClick={handleSave} disabled={!canSave}>
          <Save className="w-4 h-4 mr-2" />
          Save Draft
        </Button>

        <Button onClick={handleDeploy} disabled={!canSave}>
          <Play className="w-4 h-4 mr-2" />
          Deploy
        </Button>
      </header>

      {/* Step indicator (for NLP mode) */}
      {mode === 'nlp' && (
        <div className="flex items-center justify-center gap-4 py-3 bg-white border-b border-gray-200">
          {(['describe', 'configure', 'review', 'deploy'] as BuilderStep[]).map(
            (s, index) => {
              const isActive = step === s;
              const isPast =
                ['describe', 'configure', 'review', 'deploy'].indexOf(step) >
                index;

              return (
                <div key={s} className="flex items-center gap-2">
                  {index > 0 && (
                    <div
                      className={`w-12 h-0.5 ${
                        isPast ? 'bg-primary-500' : 'bg-gray-200'
                      }`}
                    />
                  )}
                  <button
                    onClick={() => setStep(s)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary-100 text-primary-700'
                        : isPast
                        ? 'text-primary-600'
                        : 'text-gray-500'
                    }`}
                  >
                    <span
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                        isActive
                          ? 'bg-primary-500 text-white'
                          : isPast
                          ? 'bg-primary-100 text-primary-600'
                          : 'bg-gray-200 text-gray-500'
                      }`}
                    >
                      {index + 1}
                    </span>
                    {STEP_LABELS[s]}
                  </button>
                </div>
              );
            }
          )}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Primary panel */}
        <div className={`flex-1 flex flex-col overflow-hidden ${showEditor ? 'w-2/3' : 'w-full'}`}>
          {mode === 'nlp' && (
            <div className="flex-1 flex overflow-hidden">
              <div className="flex-1 overflow-hidden">
                <NLPBuilder onComplete={() => setStep('review')} />
              </div>

              {/* Preview panel (when agent is defined) */}
              {agentDefinition && step !== 'describe' && (
                <div className="w-1/2 border-l border-gray-200 bg-white overflow-hidden">
                  <div className="h-full flex flex-col">
                    <div className="flex items-center gap-2 p-3 border-b border-gray-200">
                      <Eye className="w-4 h-4 text-gray-500" />
                      <span className="text-sm font-medium text-gray-700">Preview</span>
                    </div>
                    <div className="flex-1 overflow-auto">
                      <YAMLEditor readOnly />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {mode === 'visual' && (
            <FlowBuilder onNodeSelect={handleNodeSelect} />
          )}

          {mode === 'yaml' && (
            <YAMLEditor onSyncToVisual={() => setMode('visual')} />
          )}
        </div>

        {/* Editor sidebar */}
        {showEditor && editorNodeId && mode === 'visual' && (
          <div className="w-1/3 max-w-md">
            <AgentEditor
              nodeId={editorNodeId}
              nodeType={editorNodeType}
              onClose={() => {
                setShowEditor(false);
                setEditorNodeId(null);
              }}
            />
          </div>
        )}
      </div>

      {/* Help button */}
      <button
        className="fixed bottom-6 right-6 p-3 bg-primary-600 text-white rounded-full shadow-lg hover:bg-primary-700 transition-colors"
        title="Help"
      >
        <HelpCircle className="w-5 h-5" />
      </button>
    </div>
  );
}
