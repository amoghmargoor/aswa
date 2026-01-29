import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';
import type {
  Agent,
  TriggerDefinition,
  ActionDefinition,
  ConditionDefinition,
  ConversationMessage,
  ClarificationQuestion,
  AgentDefinitionPreview,
} from '@/types';

export type BuilderMode = 'nlp' | 'visual' | 'yaml';
export type BuilderStep = 'describe' | 'configure' | 'review' | 'deploy';

interface AgentBuilderState {
  // Current builder mode
  mode: BuilderMode;
  step: BuilderStep;

  // Session management
  sessionId: string | null;
  isSessionActive: boolean;

  // NLP conversation state
  messages: ConversationMessage[];
  currentQuestions: ClarificationQuestion[];
  isProcessing: boolean;

  // Agent definition being built
  agentDefinition: AgentDefinitionPreview | null;
  trigger: TriggerDefinition | null;
  actions: ActionDefinition[];
  conditions: ConditionDefinition[];

  // Visual builder state
  selectedNodeId: string | null;
  isConnecting: boolean;
  connectionSource: string | null;

  // YAML state
  yamlContent: string;
  yamlErrors: string[];

  // Undo/redo
  undoStack: AgentDefinitionPreview[];
  redoStack: AgentDefinitionPreview[];

  // Actions
  setMode: (mode: BuilderMode) => void;
  setStep: (step: BuilderStep) => void;
  startSession: (sessionId: string) => void;
  endSession: () => void;

  // Message actions
  addMessage: (message: Omit<ConversationMessage, 'id' | 'timestamp'>) => void;
  updateLastMessage: (updates: Partial<ConversationMessage>) => void;
  setCurrentQuestions: (questions: ClarificationQuestion[]) => void;
  setProcessing: (isProcessing: boolean) => void;
  clearConversation: () => void;

  // Definition actions
  setAgentDefinition: (definition: AgentDefinitionPreview | null) => void;
  setTrigger: (trigger: TriggerDefinition | null) => void;
  addAction: (action: ActionDefinition) => void;
  updateAction: (id: string, updates: Partial<ActionDefinition>) => void;
  removeAction: (id: string) => void;
  reorderActions: (fromIndex: number, toIndex: number) => void;
  addCondition: (condition: ConditionDefinition) => void;
  updateCondition: (id: string, updates: Partial<ConditionDefinition>) => void;
  removeCondition: (id: string) => void;

  // Visual builder actions
  selectNode: (nodeId: string | null) => void;
  startConnecting: (sourceId: string) => void;
  finishConnecting: (targetId: string) => void;
  cancelConnecting: () => void;

  // YAML actions
  setYamlContent: (content: string) => void;
  setYamlErrors: (errors: string[]) => void;
  syncFromYaml: () => void;

  // Undo/redo actions
  undo: () => void;
  redo: () => void;
  saveSnapshot: () => void;

  // Reset
  reset: () => void;
}

const initialState = {
  mode: 'nlp' as BuilderMode,
  step: 'describe' as BuilderStep,
  sessionId: null,
  isSessionActive: false,
  messages: [],
  currentQuestions: [],
  isProcessing: false,
  agentDefinition: null,
  trigger: null,
  actions: [],
  conditions: [],
  selectedNodeId: null,
  isConnecting: false,
  connectionSource: null,
  yamlContent: '',
  yamlErrors: [],
  undoStack: [],
  redoStack: [],
};

export const useAgentBuilderStore = create<AgentBuilderState>((set, get) => ({
  ...initialState,

  setMode: (mode) => set({ mode }),
  setStep: (step) => set({ step }),

  startSession: (sessionId) =>
    set({
      sessionId,
      isSessionActive: true,
      messages: [],
      currentQuestions: [],
    }),

  endSession: () =>
    set({
      sessionId: null,
      isSessionActive: false,
    }),

  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: uuidv4(),
          timestamp: new Date().toISOString(),
        },
      ],
    })),

  updateLastMessage: (updates) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0) {
        messages[messages.length - 1] = {
          ...messages[messages.length - 1],
          ...updates,
        };
      }
      return { messages };
    }),

  setCurrentQuestions: (questions) => set({ currentQuestions: questions }),
  setProcessing: (isProcessing) => set({ isProcessing }),

  clearConversation: () =>
    set({
      messages: [],
      currentQuestions: [],
      isProcessing: false,
    }),

  setAgentDefinition: (definition) => {
    const state = get();
    if (definition) {
      set({
        agentDefinition: definition,
        trigger: definition.trigger,
        actions: definition.actions,
        conditions: definition.conditions,
        yamlContent: definition.yaml,
      });
    } else {
      set({ agentDefinition: null });
    }
  },

  setTrigger: (trigger) => {
    get().saveSnapshot();
    set({ trigger });
  },

  addAction: (action) => {
    get().saveSnapshot();
    set((state) => ({
      actions: [...state.actions, { ...action, order: state.actions.length }],
    }));
  },

  updateAction: (id, updates) => {
    get().saveSnapshot();
    set((state) => ({
      actions: state.actions.map((a) =>
        a.id === id ? { ...a, ...updates } : a
      ),
    }));
  },

  removeAction: (id) => {
    get().saveSnapshot();
    set((state) => ({
      actions: state.actions
        .filter((a) => a.id !== id)
        .map((a, index) => ({
          ...a,
          order: index,
          dependsOn: a.dependsOn.filter((depId) => depId !== id),
        })),
    }));
  },

  reorderActions: (fromIndex, toIndex) => {
    get().saveSnapshot();
    set((state) => {
      const actions = [...state.actions];
      const [removed] = actions.splice(fromIndex, 1);
      actions.splice(toIndex, 0, removed);
      return {
        actions: actions.map((a, index) => ({ ...a, order: index })),
      };
    });
  },

  addCondition: (condition) => {
    get().saveSnapshot();
    set((state) => ({
      conditions: [...state.conditions, condition],
    }));
  },

  updateCondition: (id, updates) => {
    get().saveSnapshot();
    set((state) => ({
      conditions: state.conditions.map((c) =>
        c.id === id ? { ...c, ...updates } : c
      ),
    }));
  },

  removeCondition: (id) => {
    get().saveSnapshot();
    set((state) => ({
      conditions: state.conditions.filter((c) => c.id !== id),
    }));
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  startConnecting: (sourceId) =>
    set({ isConnecting: true, connectionSource: sourceId }),

  finishConnecting: (targetId) => {
    const state = get();
    if (state.connectionSource && state.connectionSource !== targetId) {
      state.updateAction(targetId, {
        dependsOn: [...(state.actions.find((a) => a.id === targetId)?.dependsOn || []), state.connectionSource],
      });
    }
    set({ isConnecting: false, connectionSource: null });
  },

  cancelConnecting: () =>
    set({ isConnecting: false, connectionSource: null }),

  setYamlContent: (content) => set({ yamlContent: content }),
  setYamlErrors: (errors) => set({ yamlErrors: errors }),

  syncFromYaml: () => {
    // This would parse the YAML and update the state
    // Implementation depends on yaml parsing library
    const state = get();
    try {
      // TODO: Parse YAML and update trigger/actions/conditions
      set({ yamlErrors: [] });
    } catch (error) {
      set({ yamlErrors: [(error as Error).message] });
    }
  },

  undo: () =>
    set((state) => {
      if (state.undoStack.length === 0) return state;
      const previous = state.undoStack[state.undoStack.length - 1];
      return {
        undoStack: state.undoStack.slice(0, -1),
        redoStack: state.agentDefinition
          ? [...state.redoStack, state.agentDefinition]
          : state.redoStack,
        agentDefinition: previous,
        trigger: previous.trigger,
        actions: previous.actions,
        conditions: previous.conditions,
        yamlContent: previous.yaml,
      };
    }),

  redo: () =>
    set((state) => {
      if (state.redoStack.length === 0) return state;
      const next = state.redoStack[state.redoStack.length - 1];
      return {
        redoStack: state.redoStack.slice(0, -1),
        undoStack: state.agentDefinition
          ? [...state.undoStack, state.agentDefinition]
          : state.undoStack,
        agentDefinition: next,
        trigger: next.trigger,
        actions: next.actions,
        conditions: next.conditions,
        yamlContent: next.yaml,
      };
    }),

  saveSnapshot: () =>
    set((state) => {
      if (!state.agentDefinition) return state;
      return {
        undoStack: [...state.undoStack.slice(-19), state.agentDefinition],
        redoStack: [],
      };
    }),

  reset: () => set(initialState),
}));
