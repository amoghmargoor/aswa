# ASWA Agent Service

AI Agent platform service for creating, managing, and executing automated agents.

## Features

- **Core Agent Framework**: Define agents with triggers, conditions, and actions
- **NLP Agent Generation**: Create agents using natural language descriptions
- **Visual Agent Builder**: Drag-and-drop flow builder interface
- **Action Blocks Library**: Pre-built actions for common integrations
- **Testing & Debugging**: Sandbox execution and test suites
- **Approval & Governance**: RBAC and approval workflows
- **Templates & Marketplace**: Reusable agent templates

## Installation

```bash
poetry install
```

## Running Tests

```bash
poetry run pytest tests/
```

## Development

```bash
poetry run uvicorn aswa_agents.main:app --reload
```
