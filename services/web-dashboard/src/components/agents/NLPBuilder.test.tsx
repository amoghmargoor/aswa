import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { NLPBuilder } from '../NLPBuilder';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';
import * as hooks from '@/hooks/useAgentGeneration';

// Mock the hooks
vi.mock('@/hooks/useAgentGeneration', () => ({
  useStartSession: vi.fn(),
  useSendMessage: vi.fn(),
  useAnswerClarification: vi.fn(),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
};

describe('NLPBuilder', () => {
  beforeEach(() => {
    // Reset store
    useAgentBuilderStore.getState().reset();

    // Mock mutations
    vi.mocked(hooks.useStartSession).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({
        id: 'session-1',
        messages: [
          { id: '1', role: 'assistant', content: 'What should trigger your agent?', timestamp: new Date().toISOString() },
        ],
        currentQuestions: [],
        isComplete: false,
        confidence: 0,
      }),
      isPending: false,
    } as any);

    vi.mocked(hooks.useSendMessage).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({
        id: 'session-1',
        messages: [
          { id: '2', role: 'assistant', content: 'Got it!', timestamp: new Date().toISOString() },
        ],
        currentQuestions: [],
        isComplete: false,
        confidence: 0.5,
      }),
      isPending: false,
    } as any);

    vi.mocked(hooks.useAnswerClarification).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({
        id: 'session-1',
        messages: [],
        currentQuestions: [],
        isComplete: true,
        confidence: 0.9,
      }),
      isPending: false,
    } as any);
  });

  it('renders empty state with examples', () => {
    render(<NLPBuilder />, { wrapper: createWrapper() });

    expect(screen.getByText('Create Your AI Agent')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Describe what your agent should do...')).toBeInTheDocument();
  });

  it('shows example prompts', () => {
    render(<NLPBuilder />, { wrapper: createWrapper() });

    expect(screen.getByText(/When I get an email/)).toBeInTheDocument();
    expect(screen.getByText(/Notify me when a critical risk/)).toBeInTheDocument();
  });

  it('submits user input', async () => {
    render(<NLPBuilder />, { wrapper: createWrapper() });

    const input = screen.getByPlaceholderText('Describe what your agent should do...');
    const submitButton = screen.getByRole('button', { name: '' }); // Send button

    fireEvent.change(input, { target: { value: 'When I get an email, summarize it' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(hooks.useStartSession().mutateAsync).toHaveBeenCalledWith('When I get an email, summarize it');
    });
  });

  it('disables input while processing', async () => {
    vi.mocked(hooks.useStartSession).mockReturnValue({
      mutateAsync: vi.fn().mockImplementation(() => new Promise(() => {})), // Never resolves
      isPending: true,
    } as any);

    const { rerender } = render(<NLPBuilder />, { wrapper: createWrapper() });

    // Set processing state
    useAgentBuilderStore.getState().setProcessing(true);
    rerender(<NLPBuilder />);

    const input = screen.getByPlaceholderText('Describe what your agent should do...');
    expect(input).toBeDisabled();
  });

  it('calls onComplete when session completes', async () => {
    const onComplete = vi.fn();
    vi.mocked(hooks.useStartSession).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({
        id: 'session-1',
        messages: [],
        currentQuestions: [],
        isComplete: true,
        confidence: 0.9,
        agentDefinition: {
          name: 'test-agent',
          displayName: 'Test Agent',
          trigger: { id: '1', type: 'email', name: 'Email', config: {} },
          actions: [],
          conditions: [],
          yaml: '',
          confidence: 0.9,
        },
      }),
      isPending: false,
    } as any);

    render(<NLPBuilder onComplete={onComplete} />, { wrapper: createWrapper() });

    const input = screen.getByPlaceholderText('Describe what your agent should do...');
    fireEvent.change(input, { target: { value: 'test' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalled();
    });
  });
});

describe('NLPBuilder Store Integration', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();
  });

  it('adds messages to store', () => {
    const store = useAgentBuilderStore.getState();

    store.addMessage({ role: 'user', content: 'Hello' });

    expect(store.messages).toHaveLength(1);
    expect(store.messages[0].role).toBe('user');
    expect(store.messages[0].content).toBe('Hello');
    expect(store.messages[0].id).toBeDefined();
    expect(store.messages[0].timestamp).toBeDefined();
  });

  it('updates last message', () => {
    const store = useAgentBuilderStore.getState();

    store.addMessage({ role: 'assistant', content: 'Loading...' });
    store.updateLastMessage({ content: 'Done!', isLoading: false });

    expect(store.messages[0].content).toBe('Done!');
    expect(store.messages[0].isLoading).toBe(false);
  });

  it('starts session correctly', () => {
    const store = useAgentBuilderStore.getState();

    store.startSession('session-123');

    expect(store.sessionId).toBe('session-123');
    expect(store.isSessionActive).toBe(true);
  });

  it('clears conversation', () => {
    const store = useAgentBuilderStore.getState();

    store.addMessage({ role: 'user', content: 'test' });
    store.setCurrentQuestions([{
      id: '1',
      type: 'missing_trigger',
      question: 'What trigger?',
      context: '',
      options: [],
      allowsCustomInput: true,
      priority: 1,
    }]);

    store.clearConversation();

    expect(store.messages).toHaveLength(0);
    expect(store.currentQuestions).toHaveLength(0);
  });
});
