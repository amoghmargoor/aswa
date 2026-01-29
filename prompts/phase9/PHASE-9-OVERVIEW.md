# Phase 9: AI Agent Platform

## Overview

Phase 9 transforms ASWA from a document intelligence platform into a full AI agent platform where users can create custom agents using natural language prompts, form builders, or visual flow editors.

**Key Outcome**: Users describe what they want in plain English → ASWA generates a working agent

---

## Phase Structure

| Sub-Phase | Description | Tasks |
|-----------|-------------|-------|
| 9.1 | Core Agent Framework | 5 tasks |
| 9.2 | NLP Agent Generation | 4 tasks |
| 9.3 | Agent Builder UI | 5 tasks |
| 9.4 | Action Blocks Library | 4 tasks |
| 9.5 | Testing & Debugging | 3 tasks |
| 9.6 | Approval & Governance | 4 tasks |
| 9.7 | Templates & Marketplace | 3 tasks |
| 9.8 | Agent Integrations | 4 tasks |
| **Total** | | **32 tasks** |

---

## Phase 9.1: Core Agent Framework (5 tasks)

Foundation for agent execution and management.

### 9.1.1 Agent Service Setup
- [ ] `prompts/phase9/task-9.1.1-agent-service-setup.md`

**Subtasks:**
- Create `services/agent-service/` directory structure
- Set up FastAPI application with health endpoints
- Configure database connections (PostgreSQL)
- Set up Redis for agent execution queue
- Add service to Docker Compose and Kubernetes configs
- Implement basic logging and metrics

**Verification:**
```bash
cd services/agent-service && pytest tests/ -v
curl http://localhost:8090/health
```

---

### 9.1.2 Agent Base Classes
- [ ] `prompts/phase9/task-9.1.2-agent-base-classes.md`

**Subtasks:**
- Define `Agent` abstract base class
- Create `ActionType` enum (create_ticket, post_message, etc.)
- Create `ActionStatus` enum (pending, executing, completed, failed)
- Create `ApprovalLevel` enum (auto, notify, approve, manual)
- Define `Action` model with parameters, confidence, reasoning
- Define `ActionResult` model for execution results
- Define `ActionContext` for execution context
- Create `Insight` model for trigger data

**Key Classes:**
```
Agent (ABC)
├── supported_insight_types: list[str]
├── required_permissions: list[str]
├── should_trigger(insight, context) -> bool
├── plan_actions(insight, context) -> list[Action]
├── execute(action, context) -> ActionResult
├── validate_action(action, context) -> bool
├── on_success(action, result, context)
└── on_failure(action, result, context)
```

---

### 9.1.3 Agent Registry
- [ ] `prompts/phase9/task-9.1.3-agent-registry.md`

**Subtasks:**
- Implement singleton `AgentRegistry` class
- Create `@register` decorator for agent classes
- Implement `get_agent(name)` method
- Implement `get_all_agents()` method
- Implement `find_agents_for_insight(insight, tenant_config)` method
- Add agent metadata (version, description, permissions)
- Support tenant-specific agent enablement

---

### 9.1.4 Agent Orchestrator
- [ ] `prompts/phase9/task-9.1.4-agent-orchestrator.md`

**Subtasks:**
- Create `AgentOrchestrator` class
- Implement `process_insight(insight, tenant_config)` method
- Implement action processing pipeline
- Handle approval level routing (auto, notify, approve, manual)
- Implement `_execute_action(agent, action, context)` method
- Implement `execute_approved_action(action_id)` for approved actions
- Add retry logic with exponential backoff
- Implement action timeout handling
- Add execution metrics and logging

---

### 9.1.5 Action Repository
- [ ] `prompts/phase9/task-9.1.5-action-repository.md`

**Subtasks:**
- Create `actions` database table
- Create `action_executions` table for history
- Implement `ActionRepository` class
- Methods: `save()`, `get()`, `update_status()`, `update_result()`
- Implement `list_pending(tenant_id)` for approval queue
- Implement `list_by_agent(agent_name)` for analytics
- Implement `list_by_insight(insight_id)` for tracing
- Add indexes for common queries

**Database Schema:**
```sql
CREATE TABLE actions (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL,
    confidence FLOAT,
    reasoning TEXT,
    insight_id UUID,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## Phase 9.2: NLP Agent Generation (4 tasks)

The core differentiator: natural language to agent definition.

### 9.2.1 Intent Extraction Pipeline
- [ ] `prompts/phase9/task-9.2.1-intent-extraction.md`

**Subtasks:**
- Create `IntentExtractor` class
- Build prompt template for intent extraction
- Extract: triggers, actions, conditions, notifications
- Handle ambiguous inputs (ask for clarification)
- Map natural language to available capabilities
- Return structured intent representation
- Add confidence scoring for extracted intents
- Handle multi-language inputs (English first)

**Example Flow:**
```
Input: "When customer emails come in, summarize and create Zendesk ticket"

Extracted Intent:
├── trigger: email_received
├── actions: [summarize, create_zendesk_ticket]
├── conditions: []
├── notifications: []
└── clarifications_needed: ["Which inbox?", "Which Zendesk project?"]
```

---

### 9.2.2 Capability Matcher
- [ ] `prompts/phase9/task-9.2.2-capability-matcher.md`

**Subtasks:**
- Create `CapabilityMatcher` class
- Maintain registry of available triggers
- Maintain registry of available actions
- Maintain registry of available integrations (per tenant)
- Match extracted intents to capabilities
- Identify missing integrations (prompt user to connect)
- Suggest alternatives for unsupported capabilities
- Return compatibility report

**Capability Registry:**
```yaml
triggers:
  - email_received
  - document_ingested
  - slack_message
  - scheduled
  - webhook
  - manual

actions:
  - summarize
  - extract_entities
  - search_knowledge_base
  - create_jira_ticket
  - create_zendesk_ticket
  - send_slack_message
  - send_email
  - update_document
```

---

### 9.2.3 Agent Definition Generator
- [ ] `prompts/phase9/task-9.2.3-agent-definition-generator.md`

**Subtasks:**
- Create `AgentDefinitionGenerator` class
- Build prompt for generating structured agent YAML
- Validate generated definition against schema
- Handle variable interpolation ({{variable}})
- Generate default error handling
- Generate default approval settings
- Add rate limiting configuration
- Return complete `AgentDefinition` object

**Output Format:**
```yaml
apiVersion: aswa.io/v1
kind: Agent
metadata:
  name: generated-agent-name
  displayName: User-Friendly Name
  description: What this agent does
spec:
  trigger: {...}
  conditions: [...]
  variables: [...]
  actions: [...]
  approval: {...}
  errorHandling: {...}
```

---

### 9.2.4 Clarification Dialog
- [ ] `prompts/phase9/task-9.2.4-clarification-dialog.md`

**Subtasks:**
- Create `ClarificationService` class
- Identify what needs clarification (targets, permissions, edge cases)
- Generate clarification questions
- Handle multi-turn conversation
- Update agent definition with clarifications
- Store conversation history for context
- Support partial agent creation (save draft)

**Clarification Types:**
- Target specification ("Which Slack channel?")
- Permission requests ("Agent needs Zendesk access")
- Edge case handling ("What if customer tier is unknown?")
- Preference choices ("Should this run automatically or require approval?")

---

## Phase 9.3: Agent Builder UI (5 tasks)

Multiple creation methods for different user types.

### 9.3.1 NLP Builder Interface
- [ ] `prompts/phase9/task-9.3.1-nlp-builder-ui.md`

**Subtasks:**
- Create "Create Agent" page with text input
- Implement real-time intent preview
- Show generated agent definition
- Handle clarification dialog inline
- Add "regenerate" option with modified prompt
- Show capability matching results
- Implement draft saving
- Add example prompts / inspiration

**UI Flow:**
```
[Text Input] → [Generate] → [Preview Agent] → [Clarify] → [Deploy]
```

---

### 9.3.2 Form-Based Builder
- [ ] `prompts/phase9/task-9.3.2-form-builder-ui.md`

**Subtasks:**
- Create guided form wizard
- Step 1: Select trigger type
- Step 2: Configure trigger (inbox, channel, schedule)
- Step 3: Select actions (multi-select)
- Step 4: Configure each action
- Step 5: Set approval mode
- Step 6: Review and deploy
- Implement form validation
- Show real-time preview of agent behavior

---

### 9.3.3 Visual Flow Builder
- [ ] `prompts/phase9/task-9.3.3-visual-flow-builder.md`

**Subtasks:**
- Integrate flow builder library (React Flow or similar)
- Create drag-and-drop canvas
- Implement trigger node types
- Implement action node types
- Implement condition node types (branching)
- Implement loop node types
- Add node configuration panels
- Implement connection validation
- Export flow to agent definition YAML
- Import existing agents to flow view

---

### 9.3.4 Agent Editor
- [ ] `prompts/phase9/task-9.3.4-agent-editor.md`

**Subtasks:**
- Create agent detail/edit page
- Show agent configuration (editable)
- Show execution history
- Show success/failure metrics
- Add enable/disable toggle
- Add delete with confirmation
- Implement version history
- Add "duplicate agent" functionality
- Show connected integrations

---

### 9.3.5 YAML Editor (Advanced)
- [ ] `prompts/phase9/task-9.3.5-yaml-editor.md`

**Subtasks:**
- Add YAML editor view for power users
- Implement syntax highlighting (Monaco editor)
- Implement schema validation with error highlighting
- Add autocomplete for actions/triggers
- Implement import/export functionality
- Add diff view for version comparison
- Support comments and documentation

---

## Phase 9.4: Action Blocks Library (4 tasks)

Extensible library of actions agents can perform.

### 9.4.1 Core Action Blocks
- [ ] `prompts/phase9/task-9.4.1-core-action-blocks.md`

**Subtasks:**
- Implement `SummarizeAction` block
- Implement `ExtractEntitiesAction` block
- Implement `ExtractActionItemsAction` block
- Implement `SearchKnowledgeBaseAction` block
- Implement `LookupCRMAction` block
- Implement `EvaluateConditionAction` block
- Create action block interface/protocol
- Add action block metadata (icon, category, config schema)

**Action Block Interface:**
```python
class ActionBlock(ABC):
    id: str
    name: str
    description: str
    category: str
    config_schema: dict

    async def execute(self, config: dict, context: ActionContext) -> ActionOutput
    async def validate_config(self, config: dict) -> ValidationResult
```

---

### 9.4.2 Integration Action Blocks
- [ ] `prompts/phase9/task-9.4.2-integration-action-blocks.md`

**Subtasks:**
- Implement `CreateJiraTicketAction`
- Implement `CreateZendeskTicketAction`
- Implement `CreateLinearIssueAction`
- Implement `SendSlackMessageAction`
- Implement `SendTeamsMessageAction`
- Implement `SendEmailAction`
- Implement `UpdateConfluencePageAction`
- Implement `UpdateNotionPageAction`
- Implement `CallWebhookAction`
- Each block handles authentication via integration service

---

### 9.4.3 Logic Action Blocks
- [ ] `prompts/phase9/task-9.4.3-logic-action-blocks.md`

**Subtasks:**
- Implement `ConditionBlock` (if/else branching)
- Implement `LoopBlock` (for each item)
- Implement `ParallelBlock` (run actions in parallel)
- Implement `DelayBlock` (wait before next action)
- Implement `SetVariableBlock` (store computed value)
- Implement `TransformBlock` (modify data with expression)
- Support nested blocks

---

### 9.4.4 Action Block Registry
- [ ] `prompts/phase9/task-9.4.4-action-block-registry.md`

**Subtasks:**
- Create `ActionBlockRegistry` singleton
- Implement `register_block()` method
- Implement `get_block(id)` method
- Implement `list_blocks(category)` method
- Implement `list_blocks_for_tenant(tenant_id)` method
- Support tenant-specific custom blocks
- Provide API endpoint to list available blocks
- Include block metadata for UI (icon, description, schema)

---

## Phase 9.5: Testing & Debugging (3 tasks)

Enable users to test agents before deployment.

### 9.5.1 Agent Test Runner
- [ ] `prompts/phase9/task-9.5.1-agent-test-runner.md`

**Subtasks:**
- Create `AgentTestRunner` class
- Accept test input data (mock trigger)
- Execute agent in "dry run" mode
- Capture all planned actions (don't execute)
- Return execution trace with timing
- Show variable values at each step
- Identify errors/exceptions
- Support test fixtures (saved test cases)

**Test Output:**
```
Execution Trace:
├─ Trigger: email_received (0.1s)
├─ Variable: email_summary (1.2s) → "Customer unable to access..."
├─ Variable: customer_tier (0.8s) → "enterprise"
├─ Action: create_ticket (SIMULATED) → {preview}
└─ Action: notify_slack (SIMULATED) → {preview}

Total: 3.4s | Errors: 0
```

---

### 9.5.2 Execution History & Logs
- [ ] `prompts/phase9/task-9.5.2-execution-history.md`

**Subtasks:**
- Create `agent_executions` table
- Log every execution with full context
- Store execution trace (steps, timing, outputs)
- Store errors with stack traces
- Implement `list_executions(agent_id)` API
- Implement `get_execution(execution_id)` API
- Add filtering by status, date range
- Add pagination for large histories
- Create execution detail UI page

---

### 9.5.3 Agent Debugging Tools
- [ ] `prompts/phase9/task-9.5.3-agent-debugging.md`

**Subtasks:**
- Add "replay execution" functionality
- Add "step through" mode (execute one action at a time)
- Add variable inspection during execution
- Show input/output for each action block
- Highlight errors in visual flow view
- Add breakpoint support (pause before action)
- Export execution logs for analysis
- Add comparison view (expected vs actual)

---

## Phase 9.6: Approval & Governance (4 tasks)

Enterprise-grade approval workflows and audit.

### 9.6.1 Approval Service
- [ ] `prompts/phase9/task-9.6.1-approval-service.md`

**Subtasks:**
- Create `ApprovalService` class
- Create `approval_requests` table
- Implement `request_approval(action, context)` method
- Implement `approve(request_id, approver_id)` method
- Implement `reject(request_id, approver_id, reason)` method
- Support approval expiration (timeout)
- Support approval delegation
- Notify approvers via Slack/email

---

### 9.6.2 Approval UI
- [ ] `prompts/phase9/task-9.6.2-approval-ui.md`

**Subtasks:**
- Create approval queue page
- Show pending approvals with details
- Allow bulk approve/reject
- Add filters (by agent, by action type)
- Show approval history
- Add one-click approve from Slack
- Add mobile-friendly approval view
- Show action preview before approving

**Slack Approval Message:**
```
🔔 Action Approval Required: Create Jira Ticket

Agent: Customer Support Handler
Target: JIRA project ENG
Confidence: 87%
Insight: Customer complaint about performance

[Approve] [Reject] [View Details]
```

---

### 9.6.3 Agent Permissions System
- [ ] `prompts/phase9/task-9.6.3-agent-permissions.md`

**Subtasks:**
- Define permission types (aswa:read, jira:write, etc.)
- Implement permission inheritance (agent ≤ creator)
- Check permissions at agent creation time
- Check permissions at execution time
- Flag high-risk permissions
- Require admin approval for high-risk agents
- Show permissions in agent UI
- Audit permission usage

---

### 9.6.4 Audit Logging for Agents
- [ ] `prompts/phase9/task-9.6.4-agent-audit-logging.md`

**Subtasks:**
- Log all agent creations/modifications
- Log all agent executions with context
- Log all approvals/rejections with approver
- Log all errors with full context
- Create audit log query API
- Create audit log export (CSV, JSON)
- Integrate with existing audit service
- Add retention policy configuration

---

## Phase 9.7: Templates & Marketplace (3 tasks)

Pre-built agents and community sharing.

### 9.7.1 Agent Template System
- [ ] `prompts/phase9/task-9.7.1-agent-templates.md`

**Subtasks:**
- Create `AgentTemplate` model
- Define template parameter schema
- Implement template instantiation
- Create initial templates:
  - Customer Support Ticket Creator
  - Document Summarizer
  - Meeting Notes → Action Items
  - Sprint Digest Generator
  - Bug Triage Agent
  - Onboarding Checklist Creator
- Add template categories
- Add template search/browse

---

### 9.7.2 Template Library UI
- [ ] `prompts/phase9/task-9.7.2-template-library-ui.md`

**Subtasks:**
- Create template gallery page
- Show template cards (name, description, category)
- Add template detail view
- Add "Use Template" flow
- Show template customization form
- Preview agent before creating
- Add template ratings/reviews
- Add "Most Popular" sorting

---

### 9.7.3 Agent Sharing (Future)
- [ ] `prompts/phase9/task-9.7.3-agent-sharing.md`

**Subtasks:**
- Enable sharing agents within organization
- Enable exporting agents as templates
- Add agent versioning
- Add template publication workflow
- Add template review/approval for marketplace
- Implement template update notifications
- Add usage analytics for shared templates

---

## Phase 9.8: Agent Integrations (4 tasks)

Connect agents to external systems.

### 9.8.1 Trigger Connectors
- [ ] `prompts/phase9/task-9.8.1-trigger-connectors.md`

**Subtasks:**
- Implement `EmailTrigger` (IMAP/webhook)
- Implement `SlackMessageTrigger`
- Implement `DocumentIngestedTrigger`
- Implement `ScheduledTrigger` (cron)
- Implement `WebhookTrigger` (inbound)
- Implement `JiraIssueTrigger` (new/updated)
- Implement `InsightDetectedTrigger`
- Create trigger connector interface
- Handle trigger authentication

---

### 9.8.2 Integration OAuth Flows
- [ ] `prompts/phase9/task-9.8.2-integration-oauth.md`

**Subtasks:**
- Extend integration service for agent use
- Add OAuth flows for new integrations:
  - Zendesk
  - Linear
  - Notion
  - HubSpot
  - Salesforce
- Store tokens securely (encrypted)
- Handle token refresh
- Show connected integrations in agent builder

---

### 9.8.3 Agent Webhooks (Outbound)
- [ ] `prompts/phase9/task-9.8.3-agent-webhooks.md`

**Subtasks:**
- Implement `CallWebhookAction` block
- Support custom HTTP methods
- Support custom headers
- Support request body templating
- Handle response processing
- Implement retry logic
- Add webhook testing tool
- Log all webhook calls

---

### 9.8.4 Agent API
- [ ] `prompts/phase9/task-9.8.4-agent-api.md`

**Subtasks:**
- Create REST API for agent management:
  - `POST /api/v1/agents` (create)
  - `GET /api/v1/agents` (list)
  - `GET /api/v1/agents/{id}` (get)
  - `PUT /api/v1/agents/{id}` (update)
  - `DELETE /api/v1/agents/{id}` (delete)
  - `POST /api/v1/agents/{id}/trigger` (manual trigger)
  - `POST /api/v1/agents/{id}/test` (test run)
- Create API for approvals
- Create API for execution history
- Add OpenAPI documentation
- Add API key authentication

---

## Phase 9 Verification

After completing all tasks:

```bash
# Run all agent service tests
cd services/agent-service && pytest tests/ -v

# Test NLP generation
curl -X POST http://localhost:8090/api/v1/agents/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "When emails arrive, summarize and create Jira ticket"}'

# Test agent execution
curl -X POST http://localhost:8090/api/v1/agents/{id}/test \
  -H "Content-Type: application/json" \
  -d '{"test_input": {...}}'

# Verify UI
npm run test --prefix services/web-dashboard
npm run build --prefix services/web-dashboard
```

---

## Dependencies

### Phase 9 depends on:
- Phase 3: Insight extraction pipeline
- Phase 4: Query service and RAG
- Phase 5: Slack/Teams integration
- Phase 6: Integration service, Jira connection
- Phase 8: Authentication, audit logging

### Services to modify:
- `web-dashboard`: Add agent builder UI
- `slack-bot`: Add approval messages
- `integration-service`: Add agent integrations
- `api-gateway`: Add agent API routes

---

## Estimated Effort

| Sub-Phase | Complexity | Estimate |
|-----------|------------|----------|
| 9.1 Core Framework | Medium | Foundation work |
| 9.2 NLP Generation | High | Core differentiator |
| 9.3 Builder UI | Medium | Multiple interfaces |
| 9.4 Action Blocks | Medium | Extensible library |
| 9.5 Testing/Debug | Medium | Essential for UX |
| 9.6 Approval/Gov | Medium | Enterprise requirement |
| 9.7 Templates | Low | Post-launch enhancement |
| 9.8 Integrations | Medium | Depends on scope |

---

## Success Criteria

Phase 9 is complete when:

1. [ ] Users can create agents via NLP prompt
2. [ ] Users can create agents via form builder
3. [ ] Users can create agents via visual flow
4. [ ] Agents can execute actions across integrations
5. [ ] Approval workflows function correctly
6. [ ] Execution history is visible and searchable
7. [ ] At least 5 agent templates are available
8. [ ] All tests pass
9. [ ] Documentation is complete

---

*Phase 9 Specification Version: 1.0*
*Last Updated: January 2026*
