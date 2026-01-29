# Task 9.3.1: NLP Builder UI

## Objective

Implement the natural language builder interface where users can describe agents in plain English and see them generated in real-time. This is the primary entry point for creating agents.

## Prerequisites

- Task 5.3.x completed (React Dashboard Setup)
- Task 9.2.x completed (NLP Generation Backend)

## Technology Stack

- React 18 with TypeScript
- TailwindCSS for styling
- React Query for API state
- Zustand for local state
- Framer Motion for animations

## Implementation

### Step 1: Agent Builder Store

```typescript
// services/web-dashboard/src/stores/agentBuilderStore.ts
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

interface ExtractedIntent {
  id: string;
  type: string;
  confidence: number;
  description: string;
  parameters: Record<string, unknown>;
  requiresClarification: boolean;
}

interface GeneratedDefinition {
  name: string;
  displayName: string;
  description: string;
  trigger: {
    type: string;
    config: Record<string, unknown>;
  };
  actions: Array<{
    id: string;
    type: string;
    config: Record<string, unknown>;
    description: string;
  }>;
  approval: {
    mode: string;
    confidenceThreshold: number;
  };
}

interface ClarificationQuestion {
  id: string;
  type: string;
  question: string;
  options?: Array<{
    id: string;
    label: string;
    description?: string;
    value: unknown;
  }>;
  allowsCustomInput: boolean;
}

interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  intents?: ExtractedIntent[];
}

interface AgentBuilderState {
  // Session
  sessionId: string | null;
  mode: 'nlp' | 'form' | 'visual' | 'yaml';

  // Conversation
  messages: ConversationMessage[];
  isProcessing: boolean;

  // Intents & Definition
  currentIntents: ExtractedIntent[];
  generatedDefinition: GeneratedDefinition | null;

  // Clarification
  pendingQuestions: ClarificationQuestion[];

  // Status
  confidence: number;
  isReady: boolean;
  error: string | null;

  // Actions
  setSessionId: (id: string) => void;
  setMode: (mode: AgentBuilderState['mode']) => void;
  addMessage: (message: ConversationMessage) => void;
  setProcessing: (processing: boolean) => void;
  setIntents: (intents: ExtractedIntent[]) => void;
  setDefinition: (definition: GeneratedDefinition | null) => void;
  setPendingQuestions: (questions: ClarificationQuestion[]) => void;
  setConfidence: (confidence: number) => void;
  setReady: (ready: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  mode: 'nlp' as const,
  messages: [],
  isProcessing: false,
  currentIntents: [],
  generatedDefinition: null,
  pendingQuestions: [],
  confidence: 0,
  isReady: false,
  error: null,
};

export const useAgentBuilderStore = create<AgentBuilderState>()(
  devtools(
    (set) => ({
      ...initialState,

      setSessionId: (id) => set({ sessionId: id }),
      setMode: (mode) => set({ mode }),
      addMessage: (message) => set((state) => ({
        messages: [...state.messages, message],
      })),
      setProcessing: (isProcessing) => set({ isProcessing }),
      setIntents: (currentIntents) => set({ currentIntents }),
      setDefinition: (generatedDefinition) => set({ generatedDefinition }),
      setPendingQuestions: (pendingQuestions) => set({ pendingQuestions }),
      setConfidence: (confidence) => set({ confidence }),
      setReady: (isReady) => set({ isReady }),
      setError: (error) => set({ error }),
      reset: () => set(initialState),
    }),
    { name: 'agent-builder' }
  )
);
```

### Step 2: API Hooks

```typescript
// services/web-dashboard/src/hooks/useAgentGeneration.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../lib/apiClient';

interface GenerateRequest {
  prompt: string;
  nameHint?: string;
}

interface SessionMessageRequest {
  message: string;
}

interface GenerateResponse {
  success: boolean;
  definition?: unknown;
  needsClarification: boolean;
  clarificationQuestions: string[];
  feasibilityIssues: string[];
  confidence: number;
}

interface SessionResponse {
  sessionId: string;
  message: string;
  isComplete: boolean;
  definition?: unknown;
}

export function useGenerateAgent() {
  return useMutation({
    mutationFn: async (request: GenerateRequest): Promise<GenerateResponse> => {
      const response = await apiClient.post('/api/v1/generate/from-prompt', {
        prompt: request.prompt,
        name_hint: request.nameHint,
      });
      return response.data;
    },
  });
}

export function useCreateSession() {
  return useMutation({
    mutationFn: async (): Promise<SessionResponse> => {
      const response = await apiClient.post('/api/v1/generate/session');
      return response.data;
    },
  });
}

export function useSendSessionMessage(sessionId: string | null) {
  return useMutation({
    mutationFn: async (request: SessionMessageRequest): Promise<SessionResponse> => {
      if (!sessionId) throw new Error('No session ID');
      const response = await apiClient.post(
        `/api/v1/generate/session/${sessionId}/message`,
        request
      );
      return response.data;
    },
  });
}

export function useCancelSession(sessionId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!sessionId) return;
      await apiClient.delete(`/api/v1/generate/session/${sessionId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
  });
}

export function useCapabilities() {
  return useQuery({
    queryKey: ['capabilities'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/registry');
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
```

### Step 3: Main NLP Builder Component

```tsx
// services/web-dashboard/src/components/agents/NLPBuilder.tsx
import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  PaperAirplaneIcon,
  SparklesIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useAgentBuilderStore } from '../../stores/agentBuilderStore';
import {
  useCreateSession,
  useSendSessionMessage,
} from '../../hooks/useAgentGeneration';
import { ConversationMessage } from './ConversationMessage';
import { IntentPreview } from './IntentPreview';
import { DefinitionPreview } from './DefinitionPreview';
import { ClarificationCard } from './ClarificationCard';
import { ConfidenceIndicator } from './ConfidenceIndicator';

export function NLPBuilder() {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    sessionId,
    messages,
    isProcessing,
    currentIntents,
    generatedDefinition,
    pendingQuestions,
    confidence,
    isReady,
    error,
    setSessionId,
    addMessage,
    setProcessing,
    setIntents,
    setDefinition,
    setPendingQuestions,
    setConfidence,
    setReady,
    setError,
    reset,
  } = useAgentBuilderStore();

  const createSession = useCreateSession();
  const sendMessage = useSendSessionMessage(sessionId);

  // Initialize session on mount
  useEffect(() => {
    if (!sessionId) {
      createSession.mutate(undefined, {
        onSuccess: (data) => {
          setSessionId(data.sessionId);
          addMessage({
            id: crypto.randomUUID(),
            role: 'assistant',
            content: data.message,
            timestamp: new Date(),
          });
        },
        onError: (err) => {
          setError('Failed to start session. Please try again.');
        },
      });
    }
  }, [sessionId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const userMessage = input.trim();
    setInput('');

    // Add user message
    addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
    });

    setProcessing(true);
    setError(null);

    try {
      const response = await sendMessage.mutateAsync({ message: userMessage });

      // Add assistant response
      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
      });

      // Update state based on response
      if (response.isComplete && response.definition) {
        setDefinition(response.definition as any);
        setReady(true);
      }

    } catch (err) {
      setError('Failed to process your message. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleReset = () => {
    reset();
    createSession.mutate(undefined, {
      onSuccess: (data) => {
        setSessionId(data.sessionId);
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.message,
          timestamp: new Date(),
        });
      },
    });
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b">
        <div className="flex items-center space-x-3">
          <SparklesIcon className="w-6 h-6 text-indigo-600" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Create Agent with AI
            </h2>
            <p className="text-sm text-gray-500">
              Describe what you want in plain English
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <ConfidenceIndicator confidence={confidence} />
          <button
            onClick={handleReset}
            className="flex items-center px-3 py-2 text-sm text-gray-600 hover:text-gray-900"
          >
            <ArrowPathIcon className="w-4 h-4 mr-1" />
            Start Over
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Conversation Panel */}
        <div className="flex flex-col flex-1">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <AnimatePresence>
              {messages.map((msg) => (
                <ConversationMessage key={msg.id} message={msg} />
              ))}
            </AnimatePresence>

            {isProcessing && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center space-x-2 text-gray-500"
              >
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce delay-100" />
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce delay-200" />
                </div>
                <span className="text-sm">Thinking...</span>
              </motion.div>
            )}

            {error && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center p-4 text-red-700 bg-red-50 rounded-lg"
              >
                <ExclamationTriangleIcon className="w-5 h-5 mr-2" />
                {error}
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 bg-white border-t">
            <form onSubmit={handleSubmit}>
              <div className="flex items-end space-x-3">
                <div className="flex-1">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe what you want your agent to do..."
                    rows={2}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    disabled={isProcessing}
                  />
                </div>
                <button
                  type="submit"
                  disabled={!input.trim() || isProcessing}
                  className="flex items-center justify-center px-4 py-3 text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <PaperAirplaneIcon className="w-5 h-5" />
                </button>
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Press Enter to send, Shift+Enter for new line
              </p>
            </form>
          </div>
        </div>

        {/* Preview Panel */}
        <div className="w-96 border-l bg-white overflow-y-auto">
          {generatedDefinition ? (
            <DefinitionPreview
              definition={generatedDefinition}
              isReady={isReady}
            />
          ) : currentIntents.length > 0 ? (
            <IntentPreview intents={currentIntents} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 p-6">
              <SparklesIcon className="w-12 h-12 mb-4" />
              <p className="text-center">
                Start describing your agent to see a preview
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

### Step 4: Supporting Components

```tsx
// services/web-dashboard/src/components/agents/ConversationMessage.tsx
import React from 'react';
import { motion } from 'framer-motion';
import { UserCircleIcon } from '@heroicons/react/24/solid';
import { SparklesIcon } from '@heroicons/react/24/outline';
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface Props {
  message: Message;
}

export function ConversationMessage({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`flex max-w-[80%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div className={`flex-shrink-0 ${isUser ? 'ml-3' : 'mr-3'}`}>
          {isUser ? (
            <UserCircleIcon className="w-8 h-8 text-gray-400" />
          ) : (
            <div className="flex items-center justify-center w-8 h-8 bg-indigo-100 rounded-full">
              <SparklesIcon className="w-5 h-5 text-indigo-600" />
            </div>
          )}
        </div>

        {/* Content */}
        <div
          className={`px-4 py-3 rounded-lg ${
            isUser
              ? 'bg-indigo-600 text-white'
              : 'bg-white border border-gray-200 text-gray-900'
          }`}
        >
          <div className={`prose prose-sm ${isUser ? 'prose-invert' : ''}`}>
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
          <p className={`text-xs mt-2 ${isUser ? 'text-indigo-200' : 'text-gray-400'}`}>
            {message.timestamp.toLocaleTimeString()}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
```

```tsx
// services/web-dashboard/src/components/agents/ConfidenceIndicator.tsx
import React from 'react';
import { motion } from 'framer-motion';

interface Props {
  confidence: number;
}

export function ConfidenceIndicator({ confidence }: Props) {
  const percentage = Math.round(confidence * 100);

  let color = 'text-gray-400';
  let bgColor = 'bg-gray-100';
  let fillColor = 'bg-gray-400';

  if (percentage >= 90) {
    color = 'text-green-600';
    bgColor = 'bg-green-100';
    fillColor = 'bg-green-500';
  } else if (percentage >= 70) {
    color = 'text-yellow-600';
    bgColor = 'bg-yellow-100';
    fillColor = 'bg-yellow-500';
  } else if (percentage >= 50) {
    color = 'text-orange-600';
    bgColor = 'bg-orange-100';
    fillColor = 'bg-orange-500';
  }

  return (
    <div className="flex items-center space-x-2">
      <span className={`text-sm font-medium ${color}`}>
        {percentage > 0 ? `${percentage}%` : '--'}
      </span>
      <div className={`w-24 h-2 rounded-full ${bgColor} overflow-hidden`}>
        <motion.div
          className={`h-full rounded-full ${fillColor}`}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      <span className="text-xs text-gray-500">confidence</span>
    </div>
  );
}
```

```tsx
// services/web-dashboard/src/components/agents/DefinitionPreview.tsx
import React from 'react';
import { motion } from 'framer-motion';
import {
  BoltIcon,
  CogIcon,
  CheckCircleIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';

interface Action {
  id: string;
  type: string;
  config: Record<string, unknown>;
  description: string;
}

interface Definition {
  name: string;
  displayName: string;
  description: string;
  trigger: {
    type: string;
    config: Record<string, unknown>;
  };
  actions: Action[];
  approval: {
    mode: string;
    confidenceThreshold: number;
  };
}

interface Props {
  definition: Definition;
  isReady: boolean;
}

export function DefinitionPreview({ definition, isReady }: Props) {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">Agent Preview</h3>
        {isReady && (
          <span className="flex items-center text-sm text-green-600">
            <CheckCircleIcon className="w-4 h-4 mr-1" />
            Ready to create
          </span>
        )}
      </div>

      {/* Name & Description */}
      <div className="mb-6">
        <h4 className="text-xl font-bold text-gray-900">{definition.displayName}</h4>
        <p className="text-sm text-gray-600 mt-1">{definition.description}</p>
      </div>

      {/* Trigger */}
      <div className="mb-6">
        <h5 className="text-sm font-medium text-gray-500 mb-2 flex items-center">
          <BoltIcon className="w-4 h-4 mr-1" />
          Trigger
        </h5>
        <div className="p-3 bg-indigo-50 rounded-lg">
          <p className="font-medium text-indigo-700 capitalize">
            {definition.trigger.type.replace(/_/g, ' ')}
          </p>
          {Object.entries(definition.trigger.config).length > 0 && (
            <ul className="mt-2 text-sm text-indigo-600">
              {Object.entries(definition.trigger.config).map(([key, value]) => (
                <li key={key}>
                  {key}: {String(value)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="mb-6">
        <h5 className="text-sm font-medium text-gray-500 mb-2 flex items-center">
          <CogIcon className="w-4 h-4 mr-1" />
          Actions ({definition.actions.length})
        </h5>
        <div className="space-y-2">
          {definition.actions.map((action, index) => (
            <motion.div
              key={action.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="flex items-center"
            >
              <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-gray-100 rounded-full text-xs font-medium text-gray-600">
                {index + 1}
              </div>
              <ArrowRightIcon className="w-4 h-4 mx-2 text-gray-400" />
              <div className="flex-1 p-3 bg-gray-50 rounded-lg">
                <p className="font-medium text-gray-900 capitalize">
                  {action.type.replace(/_/g, ' ')}
                </p>
                {action.description && (
                  <p className="text-sm text-gray-500 mt-1">{action.description}</p>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Approval Mode */}
      <div className="mb-6">
        <h5 className="text-sm font-medium text-gray-500 mb-2">Approval Mode</h5>
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
          definition.approval.mode === 'auto' ? 'bg-green-100 text-green-800' :
          definition.approval.mode === 'notify' ? 'bg-blue-100 text-blue-800' :
          definition.approval.mode === 'review' ? 'bg-yellow-100 text-yellow-800' :
          'bg-red-100 text-red-800'
        }`}>
          {definition.approval.mode.toUpperCase()}
        </span>
      </div>

      {/* Create Button */}
      {isReady && (
        <button className="w-full py-3 px-4 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors">
          Create Agent
        </button>
      )}
    </div>
  );
}
```

### Step 5: Example Prompts Component

```tsx
// services/web-dashboard/src/components/agents/ExamplePrompts.tsx
import React from 'react';
import { motion } from 'framer-motion';

interface Props {
  onSelect: (prompt: string) => void;
}

const EXAMPLE_PROMPTS = [
  {
    title: 'Email Summarizer',
    prompt: 'When I receive a support email, summarize it and post the summary to #support-alerts in Slack',
    icon: '📧',
  },
  {
    title: 'Bug Report Handler',
    prompt: 'When a bug report is detected in customer feedback, create a Jira ticket in the BUGS project',
    icon: '🐛',
  },
  {
    title: 'Weekly Digest',
    prompt: 'Every Monday at 9am, summarize all documents uploaded last week and email it to the team',
    icon: '📊',
  },
  {
    title: 'Action Item Tracker',
    prompt: 'Extract action items from meeting notes and create tasks in Linear',
    icon: '✅',
  },
];

export function ExamplePrompts({ onSelect }: Props) {
  return (
    <div className="p-6">
      <h3 className="text-sm font-medium text-gray-500 mb-4">
        Try an example to get started:
      </h3>
      <div className="grid grid-cols-2 gap-3">
        {EXAMPLE_PROMPTS.map((example, index) => (
          <motion.button
            key={example.title}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => onSelect(example.prompt)}
            className="flex items-start p-3 text-left bg-white border border-gray-200 rounded-lg hover:border-indigo-500 hover:shadow-sm transition-all"
          >
            <span className="text-2xl mr-3">{example.icon}</span>
            <div>
              <p className="font-medium text-gray-900">{example.title}</p>
              <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                {example.prompt}
              </p>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
}
```

## Test Cases

```typescript
// services/web-dashboard/src/components/agents/__tests__/NLPBuilder.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NLPBuilder } from '../NLPBuilder';

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

describe('NLPBuilder', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it('renders the NLP builder interface', () => {
    render(<NLPBuilder />, { wrapper });

    expect(screen.getByText('Create Agent with AI')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/describe what you want/i)).toBeInTheDocument();
  });

  it('shows loading state while processing', async () => {
    render(<NLPBuilder />, { wrapper });

    const input = screen.getByPlaceholderText(/describe what you want/i);
    await userEvent.type(input, 'When I get an email, summarize it');

    const submitButton = screen.getByRole('button', { name: '' }); // Paper airplane icon
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/thinking/i)).toBeInTheDocument();
    });
  });

  it('allows starting over', async () => {
    render(<NLPBuilder />, { wrapper });

    const startOverButton = screen.getByText('Start Over');
    expect(startOverButton).toBeInTheDocument();

    fireEvent.click(startOverButton);
    // Should reset the conversation
  });

  it('handles keyboard shortcuts', async () => {
    render(<NLPBuilder />, { wrapper });

    const input = screen.getByPlaceholderText(/describe what you want/i);
    await userEvent.type(input, 'Test message{enter}');

    // Should submit on Enter
    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });
});
```

```typescript
// services/web-dashboard/src/stores/__tests__/agentBuilderStore.test.ts
import { useAgentBuilderStore } from '../agentBuilderStore';

describe('agentBuilderStore', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();
  });

  it('initializes with default values', () => {
    const state = useAgentBuilderStore.getState();

    expect(state.sessionId).toBeNull();
    expect(state.messages).toEqual([]);
    expect(state.isProcessing).toBe(false);
    expect(state.confidence).toBe(0);
  });

  it('adds messages correctly', () => {
    const { addMessage } = useAgentBuilderStore.getState();

    addMessage({
      id: '1',
      role: 'user',
      content: 'Test message',
      timestamp: new Date(),
    });

    const state = useAgentBuilderStore.getState();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].content).toBe('Test message');
  });

  it('resets state correctly', () => {
    const store = useAgentBuilderStore.getState();

    store.setSessionId('test-session');
    store.setConfidence(0.95);
    store.addMessage({
      id: '1',
      role: 'user',
      content: 'Test',
      timestamp: new Date(),
    });

    store.reset();

    const newState = useAgentBuilderStore.getState();
    expect(newState.sessionId).toBeNull();
    expect(newState.messages).toEqual([]);
    expect(newState.confidence).toBe(0);
  });
});
```

## Verification Steps

1. **Run component tests:**
   ```bash
   cd services/web-dashboard
   npm test -- --testPathPattern=NLPBuilder
   ```

2. **Run Storybook:**
   ```bash
   npm run storybook
   # Navigate to Agents > NLP Builder
   ```

3. **Test in browser:**
   - Start the dashboard: `npm run dev`
   - Navigate to /agents/new
   - Enter a description like "When I get an email, summarize it"
   - Verify the conversation flows correctly

4. **Accessibility check:**
   ```bash
   npm run test:a11y
   ```

## Next Task

Proceed to `task-9.3.2-form-builder-ui.md` to implement the form-based builder interface.
