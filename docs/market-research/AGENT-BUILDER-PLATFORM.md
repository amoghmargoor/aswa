# ASWA Agent Builder Platform - No-Code AI Agent Creation

## Executive Summary

The ASWA Agent Builder Platform enables users to create custom AI agents using **natural language prompts** and simple UI options - no coding required. This transforms ASWA from a tool with pre-built agents into a **platform** where customers can build agents tailored to their unique workflows.

**Key Differentiator**: While competitors offer fixed automation, ASWA lets users describe what they want in plain English and the platform generates a working agent.

---

## Strategic Positioning

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT CREATION COMPLEXITY SPECTRUM                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   SIMPLE                                                     COMPLEX    │
│   (No-Code)                                                  (Pro-Code) │
│      │                                                           │      │
│      ▼                                                           ▼      │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐  │
│  │  NLP    │   │  Form   │   │ Visual  │   │  YAML   │   │  Code   │  │
│  │ Prompt  │   │ Builder │   │  Flow   │   │ Config  │   │   SDK   │  │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘  │
│       │             │             │             │             │         │
│       │             │             │             │             │         │
│  "Summarize    Quick setup   Drag-and-drop  Power users   Developers   │
│   customer     with guided   workflow       and admins    building     │
│   feedback     options       builder                      integrations │
│   and post                                                             │
│   to #support"                                                         │
│                                                                         │
│  ★ ASWA supports ALL levels - meet users where they are                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## User Experience: Creating an Agent

### Method 1: Natural Language Prompt (Primary)

Users describe what they want in plain English:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CREATE NEW AGENT                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Describe what you want your agent to do:                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │  "When a new customer support email comes in, summarize the      │   │
│  │   issue, check if it's a known problem in our docs, and create   │   │
│  │   a Zendesk ticket with priority based on customer tier.         │   │
│  │   Notify the #support-escalations channel if it's from an        │   │
│  │   enterprise customer."                                          │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [Generate Agent]                                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AGENT GENERATED                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ✅ I've created an agent based on your description:                    │
│                                                                         │
│  Name: Customer Support Ticket Creator                                  │
│                                                                         │
│  TRIGGER                                                                │
│  ├─ New email received in: support@company.com                          │
│  └─ Document type: Email                                                │
│                                                                         │
│  ACTIONS                                                                │
│  ├─ 1. Summarize email content                                          │
│  ├─ 2. Search knowledge base for similar issues                         │
│  ├─ 3. Look up customer tier in CRM                                     │
│  ├─ 4. Create Zendesk ticket                                            │
│  │     ├─ Priority: Based on customer tier                              │
│  │     ├─ Include: Summary + KB matches                                 │
│  │     └─ Tags: [auto-generated, aswa-agent]                            │
│  └─ 5. IF enterprise customer → Notify #support-escalations             │
│                                                                         │
│  APPROVAL MODE                                                          │
│  └─ Review before action (recommended for new agents)                   │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │   Edit Agent     │  │   Test Agent     │  │   Deploy Agent   │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Method 2: Guided Form Builder (Quick Setup)

For users who prefer structured input:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     QUICK AGENT BUILDER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. WHAT TRIGGERS THIS AGENT?                                           │
│     ○ New document uploaded                                             │
│     ● New email received                                                │
│     ○ Slack message posted                                              │
│     ○ Scheduled (daily/weekly)                                          │
│     ○ Insight detected                                                  │
│     ○ Manual trigger                                                    │
│                                                                         │
│  2. WHAT SHOULD IT DO? (select multiple)                                │
│     ☑ Summarize content                                                 │
│     ☑ Search knowledge base                                             │
│     ☐ Extract action items                                              │
│     ☑ Create ticket (Jira/Zendesk/etc)                                  │
│     ☑ Send notification                                                 │
│     ☐ Update document                                                   │
│     ☐ Schedule meeting                                                  │
│                                                                         │
│  3. WHERE TO NOTIFY?                                                    │
│     Channel: [#support-team         ▼]                                  │
│     Also DM: [@oncall-engineer      ▼]                                  │
│                                                                         │
│  4. APPROVAL REQUIRED?                                                  │
│     ○ Auto-execute all actions                                          │
│     ● Review before executing                                           │
│     ○ Suggest only (no auto-execute)                                    │
│                                                                         │
│  [Create Agent]                                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Method 3: Visual Flow Builder (Advanced)

Drag-and-drop workflow canvas:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  VISUAL AGENT BUILDER                                    [Save] [Test]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐                                                        │
│  │   TRIGGER   │                                                        │
│  │  ┌───────┐  │                                                        │
│  │  │ Email │  │                                                        │
│  │  │Received│  │                                                        │
│  │  └───┬───┘  │                                                        │
│  └──────┼──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐     ┌─────────────┐                                   │
│  │  CONDITION  │     │   ACTION    │                                   │
│  │  ┌───────┐  │     │  ┌───────┐  │                                   │
│  │  │ From  │  │ Yes │  │Summar-│  │                                   │
│  │  │Domain │──┼────►│  │  ize  │  │                                   │
│  │  │=enter-│  │     │  └───┬───┘  │                                   │
│  │  │prise? │  │     └──────┼──────┘                                   │
│  │  └───┬───┘  │            │                                          │
│  └──────┼──────┘            ▼                                          │
│         │           ┌─────────────┐     ┌─────────────┐                │
│         │    No     │   ACTION    │     │   ACTION    │                │
│         └──────────►│  ┌───────┐  │     │  ┌───────┐  │                │
│                     │  │Create │  │────►│  │ Notify│  │                │
│                     │  │Ticket │  │     │  │ Slack │  │                │
│                     │  │P: Med │  │     │  │#support│  │                │
│                     │  └───────┘  │     │  └───────┘  │                │
│                     └─────────────┘     └─────────────┘                │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│  COMPONENTS                                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │Trigger │ │Condition│ │Summarize│ │ Search │ │ Create │ │ Notify │    │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## NLP-to-Agent Generation Architecture

### How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    NLP AGENT GENERATION PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User Prompt                                                            │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  1. INTENT EXTRACTION                                            │   │
│  │     LLM analyzes prompt to extract:                              │   │
│  │     - Trigger conditions                                         │   │
│  │     - Desired actions                                            │   │
│  │     - Target systems                                             │   │
│  │     - Conditional logic                                          │   │
│  │     - Notification preferences                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  2. CAPABILITY MATCHING                                          │   │
│  │     Match extracted intent to available:                         │   │
│  │     - Trigger types (email, document, schedule, etc.)            │   │
│  │     - Action blocks (summarize, create ticket, notify, etc.)     │   │
│  │     - Integrations (Jira, Slack, Zendesk, etc.)                  │   │
│  │     - Data sources (CRM, knowledge base, etc.)                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  3. AGENT DEFINITION GENERATION                                  │   │
│  │     Generate structured agent definition:                        │   │
│  │     - YAML/JSON configuration                                    │   │
│  │     - Validation against schema                                  │   │
│  │     - Permission requirements                                    │   │
│  │     - Error handling rules                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  4. CLARIFICATION (if needed)                                    │   │
│  │     Ask user to clarify:                                         │   │
│  │     - Ambiguous targets ("which Slack channel?")                 │   │
│  │     - Missing permissions ("need Zendesk access")                │   │
│  │     - Edge cases ("what if customer tier is unknown?")           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  5. PREVIEW & DEPLOY                                             │   │
│  │     - Show user the generated agent                              │   │
│  │     - Allow edits                                                │   │
│  │     - Test with sample data                                      │   │
│  │     - Deploy with approval mode                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Intent Extraction Prompt Template

```python
AGENT_GENERATION_PROMPT = """
You are an AI agent designer. Analyze the user's request and extract a structured agent definition.

USER REQUEST:
{user_prompt}

AVAILABLE CAPABILITIES:

Triggers:
- document_ingested: New document uploaded to ASWA
- email_received: Email received at monitored inbox
- slack_message: Message posted in monitored channel
- scheduled: Time-based trigger (cron)
- insight_detected: ASWA detects specific insight type
- webhook: External system calls ASWA
- manual: User manually triggers

Actions:
- summarize: Generate summary of content
- extract_entities: Extract people, dates, topics
- extract_action_items: Find action items with owners
- search_knowledge_base: Search existing documents
- lookup_crm: Look up customer/contact in CRM
- create_jira_ticket: Create Jira issue
- create_zendesk_ticket: Create Zendesk ticket
- create_linear_issue: Create Linear issue
- update_document: Update Notion/Confluence page
- send_slack_message: Post to Slack channel
- send_teams_message: Post to Teams channel
- send_email: Send email notification
- schedule_meeting: Create calendar event
- call_webhook: Call external API

Conditions:
- contains_keywords: Content contains specific words
- sentiment_threshold: Sentiment score above/below threshold
- entity_match: Specific entity type detected
- source_match: From specific source/sender
- custom_field: Check custom metadata field

AVAILABLE INTEGRATIONS:
{available_integrations}

OUTPUT FORMAT:
Return a JSON object with this structure:
{{
  "name": "Agent name",
  "description": "What this agent does",
  "trigger": {{
    "type": "trigger_type",
    "config": {{}}
  }},
  "conditions": [
    {{
      "type": "condition_type",
      "config": {{}},
      "fail_action": "skip" | "notify" | "alternative_path"
    }}
  ],
  "actions": [
    {{
      "id": "action_1",
      "type": "action_type",
      "config": {{}},
      "depends_on": []
    }}
  ],
  "notifications": {{
    "on_success": [],
    "on_failure": []
  }},
  "approval_mode": "auto" | "review" | "suggest",
  "clarifications_needed": [
    "Question about ambiguous requirement"
  ]
}}
"""
```

---

## Agent Definition Schema

### YAML Configuration Format

```yaml
# Agent Definition Schema
apiVersion: aswa.io/v1
kind: Agent
metadata:
  name: customer-support-ticket-creator
  displayName: Customer Support Ticket Creator
  description: Creates Zendesk tickets from customer emails with priority based on tier
  version: "1.0"
  createdBy: user@company.com
  createdAt: "2026-01-29T10:00:00Z"
  tags:
    - support
    - automation
    - customer-facing

spec:
  # When does this agent run?
  trigger:
    type: email_received
    config:
      inbox: support@company.com
      filter:
        excludeAutoReplies: true
        excludeInternal: true

  # What conditions must be met?
  conditions:
    - id: not_spam
      type: spam_score
      config:
        maxScore: 0.3
      onFail: skip

  # What variables to extract/compute?
  variables:
    - name: email_summary
      action: summarize
      config:
        maxLength: 200
        style: concise

    - name: customer_tier
      action: lookup_crm
      config:
        system: salesforce
        lookupField: email
        returnField: account_tier
        default: "standard"

    - name: kb_matches
      action: search_knowledge_base
      config:
        query: "{{email_summary}}"
        limit: 3
        minScore: 0.7

    - name: is_known_issue
      action: evaluate
      config:
        expression: "len(kb_matches) > 0"

  # What actions to take?
  actions:
    - id: create_ticket
      type: create_zendesk_ticket
      config:
        subject: "{{email.subject}}"
        description: |
          ## Summary
          {{email_summary}}

          ## Customer
          - Email: {{email.from}}
          - Tier: {{customer_tier}}

          ## Related Knowledge Base Articles
          {{#each kb_matches}}
          - [{{this.title}}]({{this.url}})
          {{/each}}

          ---
          *Created by ASWA Agent*
        priority: |
          {{#if (eq customer_tier "enterprise")}}urgent
          {{else if (eq customer_tier "professional")}}high
          {{else}}normal{{/if}}
        tags:
          - aswa-generated
          - "tier-{{customer_tier}}"

    - id: notify_if_enterprise
      type: send_slack_message
      condition: "customer_tier == 'enterprise'"
      config:
        channel: "#support-escalations"
        message: |
          :rotating_light: Enterprise customer support request

          *From:* {{email.from}}
          *Subject:* {{email.subject}}
          *Ticket:* <{{actions.create_ticket.url}}|{{actions.create_ticket.id}}>

          {{email_summary}}
        mentions:
          - "@oncall-support"

  # Approval settings
  approval:
    mode: review  # auto | review | suggest
    reviewers:
      - role: support-lead
    timeout: 24h
    autoApproveAfter: null  # or duration like "4h"

  # Error handling
  errorHandling:
    onActionFailure: continue  # continue | stop | retry
    maxRetries: 3
    retryDelay: 5m
    notifyOnFailure:
      - channel: "#aswa-alerts"
        message: "Agent {{agent.name}} failed: {{error.message}}"

  # Rate limiting
  rateLimit:
    maxExecutionsPerHour: 100
    maxExecutionsPerDay: 1000

  # Permissions required
  permissions:
    - zendesk:write
    - salesforce:read
    - slack:write
    - aswa:search
```

---

## Pre-built Agent Templates

### Template Library

Users can start from templates and customize:

| Category | Template | Description | Complexity |
|----------|----------|-------------|------------|
| **Support** | Customer Ticket Creator | Email → Ticket + KB search | Medium |
| **Support** | Escalation Monitor | Detect angry customers → Alert | Simple |
| **Support** | SLA Tracker | Monitor ticket age → Remind | Simple |
| **Sales** | Lead Enrichment | New lead → Enrich + Score | Medium |
| **Sales** | Competitor Mention Alert | Docs mention competitor → Alert | Simple |
| **Sales** | Contract Renewal Reminder | 90 days before → Notify | Simple |
| **Engineering** | PR Summary | New PR → Summarize + Post | Simple |
| **Engineering** | Bug Triage | Bug report → Classify + Assign | Medium |
| **Engineering** | Sprint Digest | Weekly → Summarize progress | Medium |
| **HR** | Onboarding Checklist | New hire → Create tasks | Medium |
| **HR** | Policy Update Notifier | Policy doc changed → Notify | Simple |
| **Legal** | Contract Analyzer | New contract → Extract terms | Complex |
| **Legal** | Compliance Monitor | Doc ingested → Check compliance | Complex |
| **Product** | Feedback Synthesizer | Customer feedback → Themes | Medium |
| **Product** | Feature Request Tracker | Feedback → Create ticket | Medium |
| **General** | Meeting Summarizer | Meeting notes → Summary + Actions | Medium |
| **General** | Document Change Notifier | Doc updated → Diff + Notify | Simple |
| **General** | Weekly Digest | Scheduled → Summarize week | Medium |

### Template Format

```yaml
# Template: Customer Ticket Creator
apiVersion: aswa.io/v1
kind: AgentTemplate
metadata:
  name: customer-ticket-creator
  displayName: Customer Support Ticket Creator
  category: support
  complexity: medium
  estimatedSetupTime: 5m
  icon: ticket
  description: |
    Automatically creates support tickets from customer emails.
    Enriches tickets with customer data and knowledge base matches.

# What the user needs to configure
parameters:
  - name: inbox
    displayName: Email Inbox to Monitor
    type: email
    required: true
    description: Which inbox should trigger this agent?

  - name: ticketing_system
    displayName: Ticketing System
    type: select
    required: true
    options:
      - value: zendesk
        label: Zendesk
      - value: jira_service_desk
        label: Jira Service Desk
      - value: freshdesk
        label: Freshdesk
      - value: intercom
        label: Intercom

  - name: notification_channel
    displayName: Slack Channel for Alerts
    type: slack_channel
    required: false
    description: Optional channel for enterprise customer alerts

  - name: crm_system
    displayName: CRM for Customer Lookup
    type: select
    required: false
    options:
      - value: salesforce
        label: Salesforce
      - value: hubspot
        label: HubSpot
      - value: none
        label: Don't look up customer tier

# The actual agent spec with parameter placeholders
spec:
  trigger:
    type: email_received
    config:
      inbox: "{{parameters.inbox}}"
  # ... rest of spec using {{parameters.X}}
```

---

## Agent Testing & Debugging

### Test Mode

Before deploying, users can test agents:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     TEST AGENT                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Agent: Customer Support Ticket Creator                                 │
│                                                                         │
│  TEST INPUT                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  From: john@enterprise-client.com                                │   │
│  │  Subject: Urgent: Dashboard not loading                         │   │
│  │  Body:                                                           │   │
│  │  Our team has been unable to access the analytics dashboard     │   │
│  │  since this morning. This is blocking our quarterly review.     │   │
│  │  Please prioritize.                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [Run Test]                                                             │
│                                                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  EXECUTION TRACE                                                        │
│                                                                         │
│  ✓ Trigger: email_received                           0.1s              │
│    └─ Matched inbox: support@company.com                               │
│                                                                         │
│  ✓ Condition: not_spam                               0.2s              │
│    └─ Spam score: 0.02 (< 0.3 threshold)                               │
│                                                                         │
│  ✓ Variable: email_summary                           1.2s              │
│    └─ "Customer unable to access analytics dashboard since morning,    │
│        blocking quarterly review. Requests priority handling."         │
│                                                                         │
│  ✓ Variable: customer_tier                           0.8s              │
│    └─ Salesforce lookup: enterprise-client.com → "enterprise"          │
│                                                                         │
│  ✓ Variable: kb_matches                              0.9s              │
│    └─ Found 2 matches:                                                 │
│       - "Dashboard Loading Issues - Troubleshooting" (score: 0.89)     │
│       - "Known Issue: Dashboard Performance" (score: 0.76)             │
│                                                                         │
│  ✓ Action: create_ticket (SIMULATED)                 0.1s              │
│    └─ Would create Zendesk ticket:                                     │
│       Subject: Urgent: Dashboard not loading                           │
│       Priority: urgent (customer_tier = enterprise)                    │
│       Tags: [aswa-generated, tier-enterprise]                          │
│                                                                         │
│  ✓ Action: notify_if_enterprise (SIMULATED)          0.1s              │
│    └─ Would post to #support-escalations                               │
│       Mentions: @oncall-support                                        │
│                                                                         │
│  SUMMARY                                                                │
│  ─────────────────────────────────────────────────────────────────────  │
│  Total time: 3.4s                                                       │
│  Actions planned: 2                                                     │
│  Errors: 0                                                              │
│                                                                         │
│  [Deploy Agent]  [Edit Agent]  [Run Another Test]                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Execution History

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AGENT: Customer Support Ticket Creator                [Edit] [Pause]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  STATUS: Active                    CREATED: 2026-01-15                  │
│  EXECUTIONS: 847                   SUCCESS RATE: 99.2%                  │
│                                                                         │
│  RECENT EXECUTIONS                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │ TIME          TRIGGER           STATUS    ACTIONS       DURATION   ││
│  │ ──────────────────────────────────────────────────────────────────  ││
│  │ 10:45 AM      Email from...     ✓ Done    2 actions     2.8s       ││
│  │ 10:32 AM      Email from...     ✓ Done    1 action      2.1s       ││
│  │ 10:15 AM      Email from...     ⏸ Review  2 actions     -          ││
│  │ 09:58 AM      Email from...     ✓ Done    2 actions     3.2s       ││
│  │ 09:41 AM      Email from...     ✗ Failed  0 actions     1.5s       ││
│  │               └─ Error: Salesforce API rate limit exceeded          ││
│  └────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  [View All History]                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Action Blocks Library

### Available Actions (Extensible)

```yaml
# Action Block: Summarize
- id: summarize
  name: Summarize Content
  description: Generate a concise summary of text content
  category: ai
  icon: file-text
  config:
    maxLength:
      type: number
      default: 200
      description: Maximum summary length in words
    style:
      type: select
      options: [concise, detailed, bullet-points]
      default: concise
    focus:
      type: string
      optional: true
      description: What aspect to focus on (e.g., "action items")
  output:
    type: string
    description: The generated summary

# Action Block: Create Jira Ticket
- id: create_jira_ticket
  name: Create Jira Ticket
  description: Create a new issue in Jira
  category: ticketing
  icon: jira
  requires:
    - jira:write
  config:
    project:
      type: jira_project
      required: true
    issueType:
      type: jira_issue_type
      required: true
    summary:
      type: template
      required: true
    description:
      type: template
      required: true
    priority:
      type: jira_priority
      optional: true
    assignee:
      type: jira_user
      optional: true
    labels:
      type: array
      items: string
      optional: true
  output:
    type: object
    properties:
      key: string
      id: string
      url: string

# Action Block: Search Knowledge Base
- id: search_knowledge_base
  name: Search Knowledge Base
  description: Search ASWA's indexed documents
  category: search
  icon: search
  config:
    query:
      type: template
      required: true
    limit:
      type: number
      default: 5
    minScore:
      type: number
      default: 0.5
      min: 0
      max: 1
    filters:
      type: object
      optional: true
      properties:
        documentType:
          type: array
          items: string
        dateRange:
          type: date_range
        tags:
          type: array
          items: string
  output:
    type: array
    items:
      type: object
      properties:
        title: string
        url: string
        score: number
        snippet: string

# Action Block: Conditional
- id: condition
  name: Condition
  description: Branch based on a condition
  category: logic
  icon: git-branch
  config:
    expression:
      type: expression
      required: true
      description: JavaScript-like expression that evaluates to true/false
  branches:
    - name: then
      description: Actions if condition is true
    - name: else
      description: Actions if condition is false

# Action Block: Loop
- id: loop
  name: For Each
  description: Repeat actions for each item in a list
  category: logic
  icon: repeat
  config:
    items:
      type: variable
      required: true
      description: The list to iterate over
    itemName:
      type: string
      default: item
      description: Variable name for current item
  contains:
    - actions: Actions to repeat
```

---

## Permissions & Security

### Agent Permissions Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT PERMISSION MODEL                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  AGENT CREATOR                                                          │
│  └─ Can only use permissions they have                                  │
│  └─ Cannot grant more access than they possess                          │
│                                                                         │
│  AGENT EXECUTION                                                        │
│  └─ Runs with intersection of:                                          │
│     • Creator's permissions at creation time                            │
│     • Current organization permissions                                  │
│     • Explicitly granted agent permissions                              │
│                                                                         │
│  PERMISSION TYPES                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │ Permission          Description                 Risk Level         ││
│  │ ─────────────────────────────────────────────────────────────────  ││
│  │ aswa:read           Read ASWA documents         Low                ││
│  │ aswa:search         Search ASWA knowledge base  Low                ││
│  │ slack:read          Read Slack messages         Medium             ││
│  │ slack:write         Post to Slack               Medium             ││
│  │ jira:read           Read Jira issues            Low                ││
│  │ jira:write          Create/update Jira issues   High               ││
│  │ salesforce:read     Read CRM data               Medium             ││
│  │ email:send          Send emails                 High               ││
│  │ calendar:write      Create calendar events      Medium             ││
│  └────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  HIGH-RISK ACTIONS                                                      │
│  └─ Always require approval mode for new agents                         │
│  └─ Audit logged                                                        │
│  └─ Rate limited                                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Approval Workflow for User-Created Agents

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT APPROVAL WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. USER CREATES AGENT                                                  │
│     └─ NLP or form-based creation                                       │
│     └─ Agent saved in "draft" state                                     │
│                                                                         │
│  2. PERMISSION CHECK                                                    │
│     └─ Verify user has required permissions                             │
│     └─ Flag if agent needs elevated access                              │
│                                                                         │
│  3. ADMIN REVIEW (if required)                                          │
│     └─ High-risk actions → Admin must approve agent                     │
│     └─ Review agent logic, targets, permissions                         │
│                                                                         │
│  4. DEPLOYMENT                                                          │
│     └─ Agent deployed with approval mode = "review"                     │
│     └─ First N executions require manual approval                       │
│                                                                         │
│  5. GRADUATION                                                          │
│     └─ After N successful executions with no issues                     │
│     └─ Creator can request "auto" mode                                  │
│     └─ Admin approval for auto mode on high-risk agents                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Competitive Advantage

### Agent Builder Comparison

| Capability | Glean | Moveworks | Kore.ai | Zapier | **ASWA** |
|------------|-------|-----------|---------|--------|----------|
| NLP Agent Creation | No | No | No | No | **Yes** |
| Visual Flow Builder | No | No | Yes | Yes | **Yes** |
| Pre-built Templates | Limited | Yes | Yes | Yes | **Yes** |
| Document Intelligence | Yes | No | Limited | No | **Yes** |
| Custom Actions | No | Limited | Yes | Yes | **Yes** |
| On-Prem Deployment | No | No | Yes | No | **Yes** |
| No-Code | N/A | N/A | Partial | Yes | **Yes** |
| AI-Native | Yes | Yes | Partial | No | **Yes** |

### Key Differentiators

1. **NLP-First Creation**: "Describe what you want" → working agent
2. **Document Intelligence Built-In**: Agents can leverage ASWA's RAG and entity extraction
3. **Deployment Flexibility**: Same agent works SaaS, on-prem, or air-gapped
4. **Progressive Disclosure**: Simple → Advanced as user skill grows
5. **Enterprise Controls**: Permissions, approval workflows, audit logs

---

## Implementation Roadmap

### Phase 9A: Agent Builder Platform

| Task | Description | Priority |
|------|-------------|----------|
| 9A.1.1 | Agent definition schema (YAML) | P0 |
| 9A.1.2 | Agent runtime engine | P0 |
| 9A.1.3 | Action blocks library (core) | P0 |
| 9A.2.1 | NLP-to-agent generation | P0 |
| 9A.2.2 | Form-based builder UI | P0 |
| 9A.2.3 | Visual flow builder UI | P1 |
| 9A.3.1 | Template library (10 templates) | P0 |
| 9A.3.2 | Template customization UI | P1 |
| 9A.4.1 | Agent testing/debugging | P0 |
| 9A.4.2 | Execution history/monitoring | P0 |
| 9A.5.1 | Permission system | P0 |
| 9A.5.2 | Approval workflows | P0 |
| 9A.5.3 | Agent marketplace (community) | P2 |

---

## Example User Journeys

### Journey 1: Support Manager (No Technical Background)

```
1. Hears about ASWA from colleague
2. Logs into ASWA dashboard
3. Clicks "Create Agent"
4. Types: "Summarize customer emails and create Zendesk tickets"
5. ASWA generates agent, asks which inbox
6. User selects inbox from dropdown
7. ASWA asks which Zendesk project
8. User selects project
9. Agent created with "review" mode
10. First ticket comes in, user reviews and approves
11. After 10 successful tickets, upgrades to "auto" mode
12. Saves 30 minutes/day on ticket creation
```

### Journey 2: Engineering Lead (Technical)

```
1. Wants to automate sprint digests
2. Starts with template "Sprint Digest"
3. Customizes: adds Linear integration (not just Jira)
4. Opens YAML editor, adds custom logic
5. Tests with last week's data
6. Deploys to run every Friday at 5pm
7. Modifies over time based on team feedback
```

### Journey 3: IT Admin (Power User)

```
1. Needs agents for multiple departments
2. Creates agent templates with variables
3. Deploys same template to Sales, Support, Engineering
4. Each department customizes their instance
5. Monitors all agents from central dashboard
6. Exports agent definitions for backup/versioning
```

---

## Conclusion

The Agent Builder Platform transforms ASWA from a tool into a platform. Instead of shipping fixed agents, ASWA enables customers to create exactly what they need using natural language. This:

1. **Reduces time-to-value**: Users create agents in minutes, not months
2. **Increases stickiness**: Custom agents = higher switching costs
3. **Enables network effects**: Template marketplace creates community
4. **Scales infinitely**: Customers build for themselves, not just ASWA team

Combined with deployment flexibility (SaaS to air-gap), ASWA becomes the only enterprise AI platform that is both **powerful** and **accessible**.

---

*Document Version: 1.0*
*Last Updated: January 2026*
