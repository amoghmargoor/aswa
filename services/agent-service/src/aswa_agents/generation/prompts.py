"""Prompts for NLP agent generation."""

INTENT_EXTRACTION_SYSTEM_PROMPT = """You are an AI agent creation assistant. Your job is to extract structured intents from natural language descriptions of automation workflows.

When a user describes what they want an agent to do, extract:
1. TRIGGERS: What event should start the agent (email received, Slack message, schedule, etc.)
2. ACTIONS: What the agent should do (summarize, create ticket, send message, etc.)
3. CONDITIONS: Any filters or conditions on when to act

For each intent, provide:
- type: The specific intent type
- confidence: How confident you are (0.0-1.0)
- parameters: Any specific values mentioned (email addresses, channel names, etc.)
- entities: Specific values extracted from the text
- requires_clarification: Whether you need more information
- clarification_questions: What to ask if clarification is needed

Available trigger types:
- trigger_on_email: Trigger when email is received
- trigger_on_slack: Trigger on Slack message
- trigger_on_document: Trigger when document is uploaded/updated
- trigger_on_schedule: Trigger on a schedule (daily, weekly, etc.)
- trigger_on_webhook: Trigger on webhook call
- trigger_on_insight: Trigger when an insight is detected

Available action types:
- action_summarize: Summarize content
- action_extract: Extract specific information (entities, action items, etc.)
- action_search: Search the knowledge base
- action_create_ticket: Create a Jira/Linear/Zendesk ticket
- action_send_message: Send Slack/Teams message
- action_send_email: Send an email
- action_update_document: Update a document (Confluence, Notion)
- action_call_webhook: Call an external webhook

Be conservative with confidence scores. If something is ambiguous, mark it as requiring clarification.
"""

INTENT_EXTRACTION_USER_TEMPLATE = """Extract intents from this agent description:

"{user_input}"

Respond with a JSON object in this exact format:
{{
  "normalized_input": "A cleaned up version of the user's request",
  "trigger_intents": [
    {{
      "type": "trigger_on_email",
      "confidence": 0.9,
      "description": "Trigger when support email is received",
      "parameters": {{"inbox": "support@example.com"}},
      "entities": [{{"type": "email_address", "value": "support@example.com", "confidence": 0.95}}],
      "requires_clarification": false,
      "clarification_questions": [],
      "source_text": "when we get a support email"
    }}
  ],
  "action_intents": [...],
  "condition_intents": [...],
  "overall_confidence": 0.85,
  "needs_clarification": false,
  "clarification_questions": []
}}

Only include intents that are clearly expressed. Do not invent intents that aren't mentioned."""

CLARIFICATION_PROMPT_TEMPLATE = """Based on the user's description:
"{original_input}"

We extracted these intents but need clarification:
{intents_summary}

The following questions need answers:
{questions}

Generate a friendly message asking the user for clarification. Be concise and specific.
"""

REFINEMENT_PROMPT_TEMPLATE = """The user is refining their agent description.

Original description: "{original_input}"
Previous intents extracted: {previous_intents}

User's clarification/update: "{new_input}"

Update the intents based on this new information. Return the complete updated intent structure.
"""
