"""Prometheus metrics for Agent Service."""

from prometheus_client import Counter, Histogram, Gauge


# Agent metrics
AGENTS_TOTAL = Gauge(
    "aswa_agents_total",
    "Total number of registered agents",
    ["tenant_id", "status"],
)

AGENT_EXECUTIONS_TOTAL = Counter(
    "aswa_agent_executions_total",
    "Total number of agent executions",
    ["tenant_id", "agent_name", "status"],
)

AGENT_EXECUTION_DURATION = Histogram(
    "aswa_agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["tenant_id", "agent_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# Action metrics
ACTION_EXECUTIONS_TOTAL = Counter(
    "aswa_action_executions_total",
    "Total number of action block executions",
    ["tenant_id", "action_type", "status"],
)

ACTION_EXECUTION_DURATION = Histogram(
    "aswa_action_execution_duration_seconds",
    "Action block execution duration in seconds",
    ["action_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Approval metrics
APPROVALS_PENDING = Gauge(
    "aswa_approvals_pending",
    "Number of pending approval requests",
    ["tenant_id"],
)

APPROVALS_TOTAL = Counter(
    "aswa_approvals_total",
    "Total number of approval decisions",
    ["tenant_id", "decision"],
)

# NLP Generation metrics
NLP_GENERATIONS_TOTAL = Counter(
    "aswa_nlp_generations_total",
    "Total number of NLP agent generation requests",
    ["tenant_id", "status"],
)

NLP_GENERATION_DURATION = Histogram(
    "aswa_nlp_generation_duration_seconds",
    "NLP agent generation duration in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)
