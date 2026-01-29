"""Initial schema for agent service.

Revision ID: 001
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agents table
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('definition', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('tags', postgresql.JSONB(), nullable=True, server_default='[]'),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_execution_at', sa.DateTime(), nullable=True),
        sa.Column('execution_count', sa.Integer(), server_default='0'),
        sa.Column('success_count', sa.Integer(), server_default='0'),
        sa.Column('failure_count', sa.Integer(), server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_agent_tenant_name'),
    )
    op.create_index('ix_agents_tenant_id', 'agents', ['tenant_id'])
    op.create_index('ix_agents_status', 'agents', ['status'])
    op.create_index('ix_agent_tenant_status', 'agents', ['tenant_id', 'status'])
    op.create_index('ix_agent_tenant_created', 'agents', ['tenant_id', 'created_at'])

    # Executions table
    op.create_table(
        'executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_data', postgresql.JSONB(), nullable=False),
        sa.Column('context', postgresql.JSONB(), nullable=True),
        sa.Column('variables', postgresql.JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('dry_run', sa.Boolean(), server_default='false'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_executions_tenant_id', 'executions', ['tenant_id'])
    op.create_index('ix_executions_status', 'executions', ['status'])
    op.create_index('ix_execution_tenant_status', 'executions', ['tenant_id', 'status'])
    op.create_index('ix_execution_agent_started', 'executions', ['agent_id', 'started_at'])
    op.create_index('ix_execution_tenant_started', 'executions', ['tenant_id', 'started_at'])

    # Actions table
    op.create_table(
        'actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_system', sa.String(50), nullable=False),
        sa.Column('parameters', postgresql.JSONB(), nullable=True),
        sa.Column('confidence', sa.Float(), server_default='1.0'),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('requires_approval', sa.String(20), nullable=False, server_default='review'),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('sequence_order', sa.Integer(), server_default='0'),
        sa.Column('result_data', postgresql.JSONB(), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('external_url', sa.String(1000), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('retries_used', sa.Integer(), server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approval_comment', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_actions_tenant_id', 'actions', ['tenant_id'])
    op.create_index('ix_actions_action_type', 'actions', ['action_type'])
    op.create_index('ix_actions_status', 'actions', ['status'])
    op.create_index('ix_action_execution_sequence', 'actions', ['execution_id', 'sequence_order'])
    op.create_index('ix_action_tenant_status', 'actions', ['tenant_id', 'status'])
    op.create_index('ix_action_awaiting_approval', 'actions', ['tenant_id', 'status', 'requires_approval'])

    # Approvals table
    op.create_table(
        'approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('requested_by', sa.String(100), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('reviewers', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('decided_by', sa.String(100), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), server_default='false'),
        sa.Column('reminder_count', sa.Integer(), server_default='0'),
        sa.Column('last_reminder_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['action_id'], ['actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approvals_tenant_id', 'approvals', ['tenant_id'])
    op.create_index('ix_approvals_status', 'approvals', ['status'])
    op.create_index('ix_approval_tenant_status', 'approvals', ['tenant_id', 'status'])
    op.create_index('ix_approval_pending_expires', 'approvals', ['status', 'expires_at'])

    # Agent templates table
    op.create_table(
        'agent_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False, server_default='general'),
        sa.Column('icon', sa.String(50), server_default='bot'),
        sa.Column('definition', postgresql.JSONB(), nullable=False),
        sa.Column('variables', postgresql.JSONB(), nullable=True, server_default='[]'),
        sa.Column('is_builtin', sa.Boolean(), server_default='false'),
        sa.Column('is_public', sa.Boolean(), server_default='false'),
        sa.Column('tenant_id', sa.String(100), nullable=True),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_agent_templates_tenant_id', 'agent_templates', ['tenant_id'])
    op.create_index('ix_template_category', 'agent_templates', ['category'])
    op.create_index('ix_template_tenant_public', 'agent_templates', ['tenant_id', 'is_public'])


def downgrade() -> None:
    op.drop_table('agent_templates')
    op.drop_table('approvals')
    op.drop_table('actions')
    op.drop_table('executions')
    op.drop_table('agents')
