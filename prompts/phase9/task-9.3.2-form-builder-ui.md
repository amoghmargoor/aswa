# Task 9.3.2: Form Builder UI

## Objective

Implement a guided form-based interface for users who prefer structured input over natural language. This provides an alternative to NLP-based agent creation.

## Prerequisites

- Task 9.3.1 completed (NLP Builder UI)

## Implementation

### Step 1: Form Builder Component

```tsx
// services/web-dashboard/src/components/agents/FormBuilder.tsx
import React, { useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRightIcon, ChevronLeftIcon } from '@heroicons/react/24/outline';

import { TriggerSelector } from './form/TriggerSelector';
import { ActionBuilder } from './form/ActionBuilder';
import { ConditionBuilder } from './form/ConditionBuilder';
import { ApprovalSettings } from './form/ApprovalSettings';
import { ReviewStep } from './form/ReviewStep';
import { useCapabilities } from '../../hooks/useAgentGeneration';

const agentSchema = z.object({
  name: z.string().min(3).max(50).regex(/^[a-z0-9-]+$/),
  displayName: z.string().min(3).max(100),
  description: z.string().max(500).optional(),
  trigger: z.object({
    type: z.string(),
    config: z.record(z.unknown()),
  }),
  actions: z.array(z.object({
    id: z.string(),
    type: z.string(),
    config: z.record(z.unknown()),
  })).min(1),
  conditions: z.array(z.object({
    expression: z.string(),
  })).optional(),
  approval: z.object({
    mode: z.enum(['auto', 'notify', 'review', 'manual']),
    timeoutHours: z.number().min(1).max(168),
  }),
});

type AgentFormData = z.infer<typeof agentSchema>;

const STEPS = [
  { id: 'trigger', title: 'When', description: 'Choose what triggers this agent' },
  { id: 'conditions', title: 'If', description: 'Add conditions (optional)' },
  { id: 'actions', title: 'Then', description: 'Define what actions to take' },
  { id: 'approval', title: 'Approval', description: 'Configure approval settings' },
  { id: 'review', title: 'Review', description: 'Review and create your agent' },
];

export function FormBuilder() {
  const [currentStep, setCurrentStep] = useState(0);
  const { data: capabilities, isLoading } = useCapabilities();

  const form = useForm<AgentFormData>({
    resolver: zodResolver(agentSchema),
    defaultValues: {
      name: '',
      displayName: '',
      description: '',
      trigger: { type: '', config: {} },
      actions: [],
      conditions: [],
      approval: { mode: 'review', timeoutHours: 24 },
    },
  });

  const goNext = () => setCurrentStep((s) => Math.min(s + 1, STEPS.length - 1));
  const goPrev = () => setCurrentStep((s) => Math.max(s - 1, 0));

  const onSubmit = async (data: AgentFormData) => {
    console.log('Creating agent:', data);
    // API call to create agent
  };

  if (isLoading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Progress Steps */}
      <nav className="mb-8">
        <ol className="flex items-center">
          {STEPS.map((step, index) => (
            <li key={step.id} className="flex items-center">
              <button
                onClick={() => setCurrentStep(index)}
                disabled={index > currentStep + 1}
                className={`flex items-center ${
                  index <= currentStep
                    ? 'text-indigo-600'
                    : 'text-gray-400'
                }`}
              >
                <span className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
                  index < currentStep
                    ? 'bg-indigo-600 border-indigo-600 text-white'
                    : index === currentStep
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-gray-300'
                }`}>
                  {index < currentStep ? '✓' : index + 1}
                </span>
                <span className="ml-2 text-sm font-medium hidden sm:inline">
                  {step.title}
                </span>
              </button>
              {index < STEPS.length - 1 && (
                <ChevronRightIcon className="w-5 h-5 mx-4 text-gray-400" />
              )}
            </li>
          ))}
        </ol>
      </nav>

      {/* Step Content */}
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white rounded-lg shadow-sm border p-6"
          >
            <h2 className="text-xl font-semibold mb-2">{STEPS[currentStep].title}</h2>
            <p className="text-gray-600 mb-6">{STEPS[currentStep].description}</p>

            {currentStep === 0 && (
              <Controller
                name="trigger"
                control={form.control}
                render={({ field }) => (
                  <TriggerSelector
                    value={field.value}
                    onChange={field.onChange}
                    capabilities={capabilities?.agents.filter((c: any) => c.category === 'trigger')}
                  />
                )}
              />
            )}

            {currentStep === 1 && (
              <Controller
                name="conditions"
                control={form.control}
                render={({ field }) => (
                  <ConditionBuilder
                    conditions={field.value || []}
                    onChange={field.onChange}
                  />
                )}
              />
            )}

            {currentStep === 2 && (
              <Controller
                name="actions"
                control={form.control}
                render={({ field }) => (
                  <ActionBuilder
                    actions={field.value}
                    onChange={field.onChange}
                    capabilities={capabilities?.agents.filter((c: any) => c.category !== 'trigger')}
                  />
                )}
              />
            )}

            {currentStep === 3 && (
              <Controller
                name="approval"
                control={form.control}
                render={({ field }) => (
                  <ApprovalSettings
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
            )}

            {currentStep === 4 && (
              <ReviewStep
                data={form.getValues()}
                errors={form.formState.errors}
              />
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation Buttons */}
        <div className="flex justify-between mt-6">
          <button
            type="button"
            onClick={goPrev}
            disabled={currentStep === 0}
            className="flex items-center px-4 py-2 text-gray-600 hover:text-gray-900 disabled:opacity-50"
          >
            <ChevronLeftIcon className="w-5 h-5 mr-1" />
            Previous
          </button>

          {currentStep < STEPS.length - 1 ? (
            <button
              type="button"
              onClick={goNext}
              className="flex items-center px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Next
              <ChevronRightIcon className="w-5 h-5 ml-1" />
            </button>
          ) : (
            <button
              type="submit"
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              Create Agent
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
```

### Step 2: Trigger Selector Component

```tsx
// services/web-dashboard/src/components/agents/form/TriggerSelector.tsx
import React from 'react';
import { RadioGroup } from '@headlessui/react';
import { CheckCircleIcon } from '@heroicons/react/24/solid';

interface TriggerOption {
  id: string;
  name: string;
  description: string;
  icon: string;
  requiredConnectors: string[];
}

interface Props {
  value: { type: string; config: Record<string, unknown> };
  onChange: (value: { type: string; config: Record<string, unknown> }) => void;
  capabilities: TriggerOption[];
}

const TRIGGER_ICONS: Record<string, string> = {
  email: '📧',
  slack: '💬',
  document: '📄',
  schedule: '⏰',
  webhook: '🔗',
  insight: '💡',
};

export function TriggerSelector({ value, onChange, capabilities = [] }: Props) {
  const triggers: TriggerOption[] = capabilities.length > 0 ? capabilities : [
    { id: 'email', name: 'Email', description: 'When an email is received', icon: '📧', requiredConnectors: ['email'] },
    { id: 'slack', name: 'Slack Message', description: 'When a Slack message is posted', icon: '💬', requiredConnectors: ['slack'] },
    { id: 'document', name: 'Document Upload', description: 'When a document is uploaded', icon: '📄', requiredConnectors: [] },
    { id: 'schedule', name: 'Schedule', description: 'Run on a schedule', icon: '⏰', requiredConnectors: [] },
    { id: 'webhook', name: 'Webhook', description: 'When a webhook is called', icon: '🔗', requiredConnectors: [] },
  ];

  return (
    <RadioGroup
      value={value.type}
      onChange={(type) => onChange({ type, config: {} })}
    >
      <div className="grid grid-cols-2 gap-4">
        {triggers.map((trigger) => (
          <RadioGroup.Option
            key={trigger.id}
            value={trigger.id}
            className={({ checked }) =>
              `relative flex cursor-pointer rounded-lg border p-4 focus:outline-none ${
                checked
                  ? 'border-indigo-600 bg-indigo-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`
            }
          >
            {({ checked }) => (
              <>
                <div className="flex items-center">
                  <span className="text-2xl mr-3">
                    {TRIGGER_ICONS[trigger.id] || '⚡'}
                  </span>
                  <div>
                    <RadioGroup.Label className="font-medium text-gray-900">
                      {trigger.name}
                    </RadioGroup.Label>
                    <RadioGroup.Description className="text-sm text-gray-500">
                      {trigger.description}
                    </RadioGroup.Description>
                  </div>
                </div>
                {checked && (
                  <CheckCircleIcon className="absolute right-4 top-4 h-5 w-5 text-indigo-600" />
                )}
              </>
            )}
          </RadioGroup.Option>
        ))}
      </div>
    </RadioGroup>
  );
}
```

### Step 3: Action Builder Component

```tsx
// services/web-dashboard/src/components/agents/form/ActionBuilder.tsx
import React from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { PlusIcon, TrashIcon, Bars3Icon } from '@heroicons/react/24/outline';

interface Action {
  id: string;
  type: string;
  config: Record<string, unknown>;
}

interface Props {
  actions: Action[];
  onChange: (actions: Action[]) => void;
  capabilities: any[];
}

const ACTION_TYPES = [
  { id: 'summarize', name: 'Summarize', description: 'Create a summary', icon: '📝' },
  { id: 'extract', name: 'Extract', description: 'Extract information', icon: '🔍' },
  { id: 'send_slack', name: 'Send to Slack', description: 'Post a message', icon: '💬' },
  { id: 'send_email', name: 'Send Email', description: 'Send an email', icon: '📧' },
  { id: 'create_ticket', name: 'Create Ticket', description: 'Create a Jira/Linear ticket', icon: '🎫' },
];

export function ActionBuilder({ actions, onChange, capabilities }: Props) {
  const addAction = (type: string) => {
    const newAction: Action = {
      id: `action_${Date.now()}`,
      type,
      config: {},
    };
    onChange([...actions, newAction]);
  };

  const removeAction = (id: string) => {
    onChange(actions.filter((a) => a.id !== id));
  };

  const handleDragEnd = (result: any) => {
    if (!result.destination) return;

    const items = Array.from(actions);
    const [reordered] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reordered);

    onChange(items);
  };

  return (
    <div>
      {/* Action List */}
      <DragDropContext onDragEnd={handleDragEnd}>
        <Droppable droppableId="actions">
          {(provided) => (
            <div
              {...provided.droppableProps}
              ref={provided.innerRef}
              className="space-y-3 mb-6"
            >
              {actions.map((action, index) => (
                <Draggable key={action.id} draggableId={action.id} index={index}>
                  {(provided) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.draggableProps}
                      className="flex items-center bg-gray-50 border rounded-lg p-4"
                    >
                      <div
                        {...provided.dragHandleProps}
                        className="mr-3 cursor-grab"
                      >
                        <Bars3Icon className="w-5 h-5 text-gray-400" />
                      </div>
                      <span className="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-indigo-100 rounded-full text-sm font-medium text-indigo-600">
                        {index + 1}
                      </span>
                      <div className="ml-3 flex-1">
                        <p className="font-medium text-gray-900 capitalize">
                          {action.type.replace(/_/g, ' ')}
                        </p>
                      </div>
                      <button
                        onClick={() => removeAction(action.id)}
                        className="p-1 text-gray-400 hover:text-red-500"
                      >
                        <TrashIcon className="w-5 h-5" />
                      </button>
                    </div>
                  )}
                </Draggable>
              ))}
              {provided.placeholder}
            </div>
          )}
        </Droppable>
      </DragDropContext>

      {/* Add Action */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Add an action:</h4>
        <div className="grid grid-cols-3 gap-3">
          {ACTION_TYPES.map((actionType) => (
            <button
              key={actionType.id}
              type="button"
              onClick={() => addAction(actionType.id)}
              className="flex items-center p-3 border border-dashed border-gray-300 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition-colors"
            >
              <span className="text-xl mr-2">{actionType.icon}</span>
              <span className="text-sm font-medium text-gray-700">
                {actionType.name}
              </span>
            </button>
          ))}
        </div>
      </div>

      {actions.length === 0 && (
        <p className="mt-4 text-sm text-gray-500 text-center py-8 bg-gray-50 rounded-lg">
          Add at least one action for your agent to perform
        </p>
      )}
    </div>
  );
}
```

## Test Cases

```typescript
// services/web-dashboard/src/components/agents/__tests__/FormBuilder.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FormBuilder } from '../FormBuilder';

describe('FormBuilder', () => {
  const queryClient = new QueryClient();

  it('renders all step indicators', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <FormBuilder />
      </QueryClientProvider>
    );

    expect(screen.getByText('When')).toBeInTheDocument();
    expect(screen.getByText('Then')).toBeInTheDocument();
    expect(screen.getByText('Review')).toBeInTheDocument();
  });

  it('navigates between steps', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <FormBuilder />
      </QueryClientProvider>
    );

    // Start on step 1
    expect(screen.getByText('Choose what triggers this agent')).toBeInTheDocument();

    // Go to next step
    fireEvent.click(screen.getByText('Next'));

    // Should be on step 2
    expect(screen.getByText('Add conditions (optional)')).toBeInTheDocument();
  });

  it('validates before submission', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <FormBuilder />
      </QueryClientProvider>
    );

    // Navigate to review step
    for (let i = 0; i < 4; i++) {
      fireEvent.click(screen.getByText('Next'));
    }

    // Try to submit without required fields
    fireEvent.click(screen.getByText('Create Agent'));

    // Should show validation errors
  });
});
```

## Verification Steps

1. **Run tests:**
   ```bash
   npm test -- --testPathPattern=FormBuilder
   ```

2. **Test in browser:**
   - Navigate to /agents/new
   - Switch to Form mode
   - Complete each step
   - Verify agent creation

## Next Task

Proceed to `task-9.3.3-visual-flow-builder.md` for the visual flow builder.
