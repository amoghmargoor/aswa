import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FlowBuilder } from '../FlowBuilder';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';

describe('FlowBuilder', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();
  });

  it('renders empty state when no nodes', () => {
    render(<FlowBuilder />);

    expect(screen.getByText('Start Building Your Agent')).toBeInTheDocument();
    expect(screen.getByText(/Add a trigger to start/)).toBeInTheDocument();
  });

  it('shows add trigger button in empty state', () => {
    render(<FlowBuilder />);

    expect(screen.getByRole('button', { name: /Add Trigger/i })).toBeInTheDocument();
  });

  it('renders trigger node when trigger exists', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<FlowBuilder />);

    expect(screen.getByText('Email Trigger')).toBeInTheDocument();
    expect(screen.getByText('trigger')).toBeInTheDocument();
  });

  it('renders action nodes', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<FlowBuilder />);

    expect(screen.getByText('Email Trigger')).toBeInTheDocument();
    expect(screen.getByText('Summarize')).toBeInTheDocument();
  });

  it('renders condition nodes', () => {
    useAgentBuilderStore.getState().addCondition({
      id: 'condition-1',
      expression: 'confidence > 0.8',
      description: 'High confidence filter',
    });

    render(<FlowBuilder />);

    expect(screen.getByText('High confidence filter')).toBeInTheDocument();
  });

  it('opens add trigger menu on button click', () => {
    render(<FlowBuilder />);

    // Click the toolbar trigger button
    const triggerButtons = screen.getAllByRole('button', { name: /Trigger/i });
    fireEvent.click(triggerButtons[0]);

    expect(screen.getByText('Email Received')).toBeInTheDocument();
    expect(screen.getByText('Slack Message')).toBeInTheDocument();
  });

  it('adds trigger when menu item selected', () => {
    render(<FlowBuilder />);

    const triggerButtons = screen.getAllByRole('button', { name: /Trigger/i });
    fireEvent.click(triggerButtons[0]);

    fireEvent.click(screen.getByText('Email Received'));

    const state = useAgentBuilderStore.getState();
    expect(state.trigger).not.toBeNull();
    expect(state.trigger?.type).toBe('email');
  });

  it('disables add trigger when trigger exists', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<FlowBuilder />);

    const triggerButtons = screen.getAllByRole('button', { name: /Trigger/i });
    expect(triggerButtons[0]).toBeDisabled();
  });

  it('calls onNodeSelect when node clicked', () => {
    const onNodeSelect = vi.fn();
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<FlowBuilder onNodeSelect={onNodeSelect} />);

    fireEvent.click(screen.getByText('Email Trigger'));

    expect(onNodeSelect).toHaveBeenCalledWith('trigger-1', 'trigger');
  });

  it('deletes trigger when delete clicked', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });

    render(<FlowBuilder />);

    // Find and click delete button
    const deleteButtons = screen.getAllByTitle('Delete');
    fireEvent.click(deleteButtons[0]);

    const state = useAgentBuilderStore.getState();
    expect(state.trigger).toBeNull();
  });

  it('deletes action when delete clicked', () => {
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    render(<FlowBuilder />);

    const deleteButtons = screen.getAllByTitle('Delete');
    fireEvent.click(deleteButtons[0]);

    const state = useAgentBuilderStore.getState();
    expect(state.actions).toHaveLength(0);
  });

  it('shows connector lines between nodes', () => {
    useAgentBuilderStore.getState().setTrigger({
      id: 'trigger-1',
      type: 'email',
      name: 'Email Trigger',
      config: {},
    });
    useAgentBuilderStore.getState().addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    const { container } = render(<FlowBuilder />);

    // Check for connector elements (the vertical lines)
    const connectors = container.querySelectorAll('.w-0\\.5');
    expect(connectors.length).toBeGreaterThan(0);
  });
});

describe('FlowBuilder Store', () => {
  beforeEach(() => {
    useAgentBuilderStore.getState().reset();
  });

  it('adds action with correct dependencies', () => {
    const store = useAgentBuilderStore.getState();

    store.addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'Summarize',
      config: {},
      dependsOn: [],
      order: 0,
    });

    store.addAction({
      id: 'action-2',
      type: 'send_message',
      name: 'Send Slack',
      config: {},
      dependsOn: [],
      order: 1,
    });

    expect(store.actions).toHaveLength(2);
    expect(store.actions[0].order).toBe(0);
    expect(store.actions[1].order).toBe(1);
  });

  it('reorders actions correctly', () => {
    const store = useAgentBuilderStore.getState();

    store.addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'First',
      config: {},
      dependsOn: [],
      order: 0,
    });

    store.addAction({
      id: 'action-2',
      type: 'send_message',
      name: 'Second',
      config: {},
      dependsOn: [],
      order: 1,
    });

    store.reorderActions(1, 0);

    expect(store.actions[0].id).toBe('action-2');
    expect(store.actions[1].id).toBe('action-1');
    expect(store.actions[0].order).toBe(0);
    expect(store.actions[1].order).toBe(1);
  });

  it('removes action and updates dependencies', () => {
    const store = useAgentBuilderStore.getState();

    store.addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'First',
      config: {},
      dependsOn: [],
      order: 0,
    });

    store.addAction({
      id: 'action-2',
      type: 'send_message',
      name: 'Second',
      config: {},
      dependsOn: ['action-1'],
      order: 1,
    });

    store.removeAction('action-1');

    expect(store.actions).toHaveLength(1);
    expect(store.actions[0].dependsOn).not.toContain('action-1');
  });

  it('manages connecting state', () => {
    const store = useAgentBuilderStore.getState();

    store.startConnecting('source-id');

    expect(store.isConnecting).toBe(true);
    expect(store.connectionSource).toBe('source-id');

    store.cancelConnecting();

    expect(store.isConnecting).toBe(false);
    expect(store.connectionSource).toBeNull();
  });

  it('finishes connecting and adds dependency', () => {
    const store = useAgentBuilderStore.getState();

    store.addAction({
      id: 'action-1',
      type: 'summarize',
      name: 'First',
      config: {},
      dependsOn: [],
      order: 0,
    });

    store.addAction({
      id: 'action-2',
      type: 'send_message',
      name: 'Second',
      config: {},
      dependsOn: [],
      order: 1,
    });

    store.startConnecting('action-1');
    store.finishConnecting('action-2');

    expect(store.isConnecting).toBe(false);
    expect(store.actions[1].dependsOn).toContain('action-1');
  });
});
