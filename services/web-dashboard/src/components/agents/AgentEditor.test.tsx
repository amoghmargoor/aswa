import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentEditor } from './AgentEditor';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';

describe('AgentEditor', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();
  });

  it('renders nothing when node not found', () => {
    const { container } = render(
      <AgentEditor nodeId="nonexistent" nodeType="trigger" onClose={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders trigger editor when trigger node selected', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<AgentEditor nodeId="trigger-1" nodeType="trigger" onClose={() => {}} />);

    expect(screen.getByText('Edit Configuration')).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
  });

  it('renders action editor when action node selected', () => {
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<AgentEditor nodeId="action-1" nodeType="action" onClose={() => {}} />);

    expect(screen.getByText('Edit Configuration')).toBeInTheDocument();
    expect(screen.getByText('action')).toBeInTheDocument();
  });

  it('renders condition editor when condition node selected', () => {
    useAgentBuilderStore.getState().addCondition({
      id: 'condition-1',
      expression: 'confidence > 0.8',
      description: 'High confidence',
    });

    render(<AgentEditor nodeId="condition-1" nodeType="condition" onClose={() => {}} />);

    expect(screen.getByText('Edit Configuration')).toBeInTheDocument();
    expect(screen.getByLabelText('Expression')).toBeInTheDocument();
  });

  it('calls onClose when cancel clicked', () => {
    const onClose = vi.fn();
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<AgentEditor nodeId="trigger-1" nodeType="trigger" onClose={onClose} />);

    fireEvent.click(screen.getByText('Cancel'));

    expect(onClose).toHaveBeenCalled();
  });

  it('updates trigger on save', () => {
    const onClose = vi.fn();
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<AgentEditor nodeId="trigger-1" nodeType="trigger" onClose={onClose} />);

    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'Updated Name' } });

    fireEvent.click(screen.getByText('Save'));

    const state = useAgentBuilderStore.getState();
    expect(state.trigger?.name).toBe('Updated Name');
    expect(onClose).toHaveBeenCalled();
  });

  it('updates action on save', () => {
    const onClose = vi.fn();
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<AgentEditor nodeId="action-1" nodeType="action" onClose={onClose} />);

    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'New Action Name' } });

    fireEvent.click(screen.getByText('Save'));

    const state = useAgentBuilderStore.getState();
    expect(state.actions[0].name).toBe('New Action Name');
  });

  it('renders schema fields for email trigger', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<AgentEditor nodeId="trigger-1" nodeType="trigger" onClose={() => {}} />);

    expect(screen.getByLabelText('From (filter)')).toBeInTheDocument();
    expect(screen.getByLabelText('Subject contains')).toBeInTheDocument();
    expect(screen.getByLabelText('Folder')).toBeInTheDocument();
  });

  it('renders schema fields for summarize action', () => {
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<AgentEditor nodeId="action-1" nodeType="action" onClose={() => {}} />);

    expect(screen.getByLabelText('Style')).toBeInTheDocument();
    expect(screen.getByLabelText('Max length')).toBeInTheDocument();
    expect(screen.getByLabelText('Include key points')).toBeInTheDocument();
  });

  it('shows validation error for required fields', () => {
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'send_message',
      name: 'Send Slack',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<AgentEditor nodeId="action-1" nodeType="action" onClose={() => {}} />);

    // Clear the channel field and save
    fireEvent.click(screen.getByText('Save'));

    expect(screen.getByText(/Channel is required/)).toBeInTheDocument();
  });
});

describe('AgentEditor Field Types', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();
  });

  it('renders select field correctly', () => {
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<AgentEditor nodeId="action-1" nodeType="action" onClose={() => {}} />);

    const styleSelect = screen.getByLabelText('Style');
    expect(styleSelect.tagName).toBe('SELECT');
    expect(screen.getByText('Brief')).toBeInTheDocument();
    expect(screen.getByText('Detailed')).toBeInTheDocument();
  });

  it('renders boolean field as checkbox', () => {
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<AgentEditor nodeId="action-1" nodeType="action" onClose={() => {}} />);

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeInTheDocument();
  });

  it('renders number field correctly', () => {
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<AgentEditor nodeId="action-1" nodeType="action" onClose={() => {}} />);

    const numberInput = screen.getByLabelText('Max length');
    expect(numberInput).toHaveAttribute('type', 'number');
  });
});
