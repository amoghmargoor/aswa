import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { YAMLEditor } from '../YAMLEditor';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';
import * as hooks from '@/hooks/useAgentGeneration';

// Mock the hooks
vi.mock('@/hooks/useAgentGeneration', () => ({
  useValidateYaml: vi.fn(),
}));

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
});

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('YAMLEditor', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();

    vi.mocked(hooks.useValidateYaml).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({ valid: true, errors: [] }),
      isSuccess: false,
      isPending: false,
    } as any);
  });

  it('renders empty editor', () => {
    render(<YAMLEditor />, { wrapper: createWrapper() });

    expect(screen.getByText('YAML Editor')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('# Agent YAML definition...')).toBeInTheDocument();
  });

  it('displays line numbers', () => {
    useAgentBuilderStore.getState().setYamlContent('line1\nline2\nline3');

    render(<YAMLEditor />, { wrapper: createWrapper() });

    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows character count', () => {
    useAgentBuilderStore.getState().setYamlContent('test content');

    render(<YAMLEditor />, { wrapper: createWrapper() });

    expect(screen.getByText('12 characters')).toBeInTheDocument();
  });

  it('shows line count', () => {
    useAgentBuilderStore.getState().setYamlContent('line1\nline2');

    render(<YAMLEditor />, { wrapper: createWrapper() });

    expect(screen.getByText('2 lines')).toBeInTheDocument();
  });

  it('marks content as changed when edited', () => {
    useAgentBuilderStore.getState().setYamlContent('original');

    render(<YAMLEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    fireEvent.change(textarea, { target: { value: 'modified' } });

    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
  });

  it('shows apply and validate buttons when content changed', () => {
    useAgentBuilderStore.getState().setYamlContent('original');

    render(<YAMLEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    fireEvent.change(textarea, { target: { value: 'modified' } });

    expect(screen.getByText('Validate')).toBeInTheDocument();
    expect(screen.getByText('Apply Changes')).toBeInTheDocument();
  });

  it('copies content to clipboard', async () => {
    useAgentBuilderStore.getState().setYamlContent('yaml content');

    render(<YAMLEditor />, { wrapper: createWrapper() });

    const copyButton = screen.getByTitle('Copy to clipboard');
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('yaml content');
    });
  });

  it('validates YAML when validate clicked', async () => {
    const validateMock = vi.fn().mockResolvedValue({ valid: true, errors: [] });
    vi.mocked(hooks.useValidateYaml).mockReturnValue({
      mutateAsync: validateMock,
      isSuccess: false,
      isPending: false,
    } as any);

    useAgentBuilderStore.getState().setYamlContent('original');

    render(<YAMLEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    fireEvent.change(textarea, { target: { value: 'modified yaml' } });

    fireEvent.click(screen.getByText('Validate'));

    await waitFor(() => {
      expect(validateMock).toHaveBeenCalledWith('modified yaml');
    });
  });

  it('shows validation errors', () => {
    useAgentBuilderStore.getState().setYamlErrors(['Invalid syntax at line 5']);

    render(<YAMLEditor />, { wrapper: createWrapper() });

    expect(screen.getByText('Validation errors:')).toBeInTheDocument();
    expect(screen.getByText('Invalid syntax at line 5')).toBeInTheDocument();
  });

  it('shows valid status after successful validation', () => {
    vi.mocked(hooks.useValidateYaml).mockReturnValue({
      mutateAsync: vi.fn(),
      isSuccess: true,
      isPending: false,
    } as any);

    render(<YAMLEditor />, { wrapper: createWrapper() });

    expect(screen.getByText('YAML is valid')).toBeInTheDocument();
  });

  it('disables editing in read-only mode', () => {
    render(<YAMLEditor readOnly />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    expect(textarea).toHaveAttribute('readonly');
  });

  it('hides upload and regenerate buttons in read-only mode', () => {
    render(<YAMLEditor readOnly />, { wrapper: createWrapper() });

    expect(screen.queryByTitle('Upload YAML')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Regenerate from visual builder')).not.toBeInTheDocument();
  });

  it('calls onSyncToVisual when apply changes clicked', async () => {
    const onSyncToVisual = vi.fn();
    useAgentBuilderStore.getState().setYamlContent('original');

    render(<YAMLEditor onSyncToVisual={onSyncToVisual} />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    fireEvent.change(textarea, { target: { value: 'modified' } });

    fireEvent.click(screen.getByText('Apply Changes'));

    expect(onSyncToVisual).toHaveBeenCalled();
  });
});

describe('YAMLEditor YAML Generation', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();
    vi.mocked(hooks.useValidateYaml).mockReturnValue({
      mutateAsync: vi.fn(),
      isSuccess: false,
      isPending: false,
    } as any);
  });

  it('generates YAML from trigger', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: { from_filter: '@company.com' },
    });

    render(<YAMLEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    expect(textarea.textContent).toContain('trigger:');
    expect(textarea.textContent).toContain('type: email');
  });

  it('generates YAML from actions', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email',
      config: {},
    });
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: { style: 'brief' },
      dependsOn: [],
      order: 0,
    });

    render(<YAMLEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    expect(textarea.textContent).toContain('actions:');
    expect(textarea.textContent).toContain('type: summarize');
  });

  it('generates YAML from conditions', () => {
    useAgentBuilderStore.getState().addCondition({
      id: 'condition-1',
      expression: 'confidence > 0.8',
      description: 'High confidence',
    });

    render(<YAMLEditor />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText('# Agent YAML definition...');
    expect(textarea.textContent).toContain('conditions:');
    expect(textarea.textContent).toContain('confidence > 0.8');
  });
});
