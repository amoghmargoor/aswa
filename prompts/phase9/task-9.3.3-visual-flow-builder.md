# Task 9.3.3: Visual Flow Builder

## Objective

Implement a visual drag-and-drop flow builder using React Flow for creating complex agent workflows with branching logic.

## Prerequisites

- Task 9.3.1-9.3.2 completed
- React Flow library installed

## Implementation

### Step 1: Flow Builder Component

```tsx
// services/web-dashboard/src/components/agents/VisualFlowBuilder.tsx
import React, { useCallback, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { TriggerNode } from './nodes/TriggerNode';
import { ActionNode } from './nodes/ActionNode';
import { ConditionNode } from './nodes/ConditionNode';
import { NodePalette } from './NodePalette';
import { NodeEditor } from './NodeEditor';

const nodeTypes = {
  trigger: TriggerNode,
  action: ActionNode,
  condition: ConditionNode,
};

const initialNodes: Node[] = [
  {
    id: 'trigger-1',
    type: 'trigger',
    position: { x: 250, y: 50 },
    data: { label: 'Trigger', type: '', config: {} },
  },
];

const initialEdges: Edge[] = [];

export function VisualFlowBuilder() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow');

      const position = {
        x: event.clientX - 250,
        y: event.clientY - 100,
      };

      const newNode: Node = {
        id: `${type}-${Date.now()}`,
        type,
        position,
        data: { label: type, type: '', config: {} },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [setNodes]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const updateNodeData = (nodeId: string, data: any) => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, ...data } } : node
      )
    );
  };

  const exportDefinition = () => {
    const definition = {
      trigger: nodes.find((n) => n.type === 'trigger')?.data,
      actions: nodes.filter((n) => n.type === 'action').map((n) => n.data),
      conditions: nodes.filter((n) => n.type === 'condition').map((n) => n.data),
      connections: edges.map((e) => ({ from: e.source, to: e.target })),
    };
    console.log('Exported:', definition);
    return definition;
  };

  return (
    <div className="h-full flex">
      {/* Node Palette */}
      <div className="w-64 border-r bg-gray-50 p-4">
        <NodePalette />
      </div>

      {/* Flow Canvas */}
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
          <Panel position="top-right">
            <button
              onClick={exportDefinition}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg"
            >
              Save Agent
            </button>
          </Panel>
        </ReactFlow>
      </div>

      {/* Node Editor Panel */}
      {selectedNode && (
        <div className="w-80 border-l bg-white p-4">
          <NodeEditor
            node={selectedNode}
            onUpdate={(data) => updateNodeData(selectedNode.id, data)}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}
    </div>
  );
}
```

### Step 2: Custom Nodes

```tsx
// services/web-dashboard/src/components/agents/nodes/TriggerNode.tsx
import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { BoltIcon } from '@heroicons/react/24/outline';

export const TriggerNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div className={`px-4 py-3 rounded-lg border-2 bg-white shadow-sm min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-indigo-200'
    }`}>
      <div className="flex items-center">
        <div className="w-8 h-8 flex items-center justify-center bg-indigo-100 rounded-full mr-3">
          <BoltIcon className="w-5 h-5 text-indigo-600" />
        </div>
        <div>
          <p className="text-xs text-indigo-600 font-medium">TRIGGER</p>
          <p className="text-sm font-semibold text-gray-900">
            {data.type || 'Select trigger...'}
          </p>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-indigo-500" />
    </div>
  );
});

// services/web-dashboard/src/components/agents/nodes/ActionNode.tsx
import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { CogIcon } from '@heroicons/react/24/outline';

export const ActionNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div className={`px-4 py-3 rounded-lg border-2 bg-white shadow-sm min-w-[180px] ${
      selected ? 'border-green-500' : 'border-green-200'
    }`}>
      <Handle type="target" position={Position.Top} className="!bg-green-500" />
      <div className="flex items-center">
        <div className="w-8 h-8 flex items-center justify-center bg-green-100 rounded-full mr-3">
          <CogIcon className="w-5 h-5 text-green-600" />
        </div>
        <div>
          <p className="text-xs text-green-600 font-medium">ACTION</p>
          <p className="text-sm font-semibold text-gray-900">
            {data.type || 'Select action...'}
          </p>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-green-500" />
    </div>
  );
});

// services/web-dashboard/src/components/agents/nodes/ConditionNode.tsx
import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { QuestionMarkCircleIcon } from '@heroicons/react/24/outline';

export const ConditionNode = memo(({ data, selected }: NodeProps) => {
  return (
    <div className={`px-4 py-3 rounded-lg border-2 bg-white shadow-sm min-w-[180px] ${
      selected ? 'border-yellow-500' : 'border-yellow-200'
    }`}>
      <Handle type="target" position={Position.Top} className="!bg-yellow-500" />
      <div className="flex items-center">
        <div className="w-8 h-8 flex items-center justify-center bg-yellow-100 rounded-full mr-3">
          <QuestionMarkCircleIcon className="w-5 h-5 text-yellow-600" />
        </div>
        <div>
          <p className="text-xs text-yellow-600 font-medium">CONDITION</p>
          <p className="text-sm font-semibold text-gray-900">
            {data.expression || 'Set condition...'}
          </p>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        style={{ left: '30%' }}
        className="!bg-green-500"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        style={{ left: '70%' }}
        className="!bg-red-500"
      />
    </div>
  );
});
```

### Step 3: Node Palette

```tsx
// services/web-dashboard/src/components/agents/NodePalette.tsx
import React from 'react';
import { BoltIcon, CogIcon, QuestionMarkCircleIcon } from '@heroicons/react/24/outline';

const PALETTE_ITEMS = [
  { type: 'trigger', label: 'Trigger', icon: BoltIcon, color: 'indigo' },
  { type: 'action', label: 'Action', icon: CogIcon, color: 'green' },
  { type: 'condition', label: 'Condition', icon: QuestionMarkCircleIcon, color: 'yellow' },
];

export function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 mb-4">Nodes</h3>
      <div className="space-y-2">
        {PALETTE_ITEMS.map((item) => (
          <div
            key={item.type}
            draggable
            onDragStart={(e) => onDragStart(e, item.type)}
            className={`flex items-center p-3 bg-white border rounded-lg cursor-grab hover:shadow-md transition-shadow border-${item.color}-200`}
          >
            <item.icon className={`w-5 h-5 mr-3 text-${item.color}-600`} />
            <span className="text-sm font-medium text-gray-700">{item.label}</span>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-gray-500">
        Drag nodes onto the canvas to build your workflow
      </p>
    </div>
  );
}
```

## Test Cases

```typescript
// services/web-dashboard/src/components/agents/__tests__/VisualFlowBuilder.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { VisualFlowBuilder } from '../VisualFlowBuilder';

describe('VisualFlowBuilder', () => {
  it('renders initial trigger node', () => {
    render(<VisualFlowBuilder />);
    expect(screen.getByText('TRIGGER')).toBeInTheDocument();
  });

  it('shows node palette', () => {
    render(<VisualFlowBuilder />);
    expect(screen.getByText('Nodes')).toBeInTheDocument();
    expect(screen.getByText('Action')).toBeInTheDocument();
  });

  it('allows node selection', () => {
    render(<VisualFlowBuilder />);
    const triggerNode = screen.getByText('TRIGGER').closest('div');
    if (triggerNode) {
      fireEvent.click(triggerNode);
      // Node editor should appear
    }
  });
});
```

## Next Task

Proceed to `task-9.3.4-agent-editor.md` for the agent detail and edit page.
