-- ASWA Development Seed Data
-- Version: V002
-- Description: Seeds development data for testing and local development
-- WARNING: This migration should ONLY run in development environments

-- ============================================================================
-- IMPORTANT: Development Only
-- ============================================================================
-- This seed data is for LOCAL DEVELOPMENT ONLY.
-- Do NOT run this migration in production or staging environments.
-- The migration framework should be configured to skip this in non-dev environments.
-- ============================================================================

-- Demo Tenant
-- Fixed UUID for consistency across dev environments
INSERT INTO tenants (id, name, slug, settings, status, created_at, updated_at)
VALUES (
    '123e4567-e89b-12d3-a456-426614174000',
    'Demo Company',
    'demo',
    '{"theme": "light", "timezone": "America/New_York", "language": "en"}',
    'active',
    NOW(),
    NOW()
);

COMMENT ON TABLE tenants IS 'Demo tenant for development and testing';

-- Demo Admin User
INSERT INTO users (id, tenant_id, email, name, role, status, settings, created_at, updated_at)
VALUES (
    '223e4567-e89b-12d3-a456-426614174001',
    '123e4567-e89b-12d3-a456-426614174000',
    'admin@demo.aswa.com',
    'Demo Admin',
    'admin',
    'active',
    '{"notifications_enabled": true, "email_frequency": "realtime"}',
    NOW(),
    NOW()
);

-- Demo Regular User
INSERT INTO users (id, tenant_id, email, name, role, status, settings, created_at, updated_at)
VALUES (
    '223e4567-e89b-12d3-a456-426614174002',
    '123e4567-e89b-12d3-a456-426614174000',
    'user@demo.aswa.com',
    'Demo User',
    'member',
    'active',
    '{"notifications_enabled": true, "email_frequency": "daily"}',
    NOW(),
    NOW()
);

-- Demo Manager User
INSERT INTO users (id, tenant_id, email, name, role, status, settings, created_at, updated_at)
VALUES (
    '223e4567-e89b-12d3-a456-426614174003',
    '123e4567-e89b-12d3-a456-426614174000',
    'manager@demo.aswa.com',
    'Demo Manager',
    'manager',
    'active',
    '{"notifications_enabled": true, "email_frequency": "hourly"}',
    NOW(),
    NOW()
);

-- Demo Data Source (Gmail)
-- Note: credentials_encrypted is NULL in demo - would need actual encrypted credentials
INSERT INTO data_sources (
    id,
    tenant_id,
    source_type,
    name,
    config,
    credentials_encrypted,
    status,
    sync_frequency_minutes,
    created_at,
    updated_at
)
VALUES (
    '323e4567-e89b-12d3-a456-426614174100',
    '123e4567-e89b-12d3-a456-426614174000',
    'gmail',
    'Demo Gmail Account',
    '{"email": "demo@example.com", "labels": ["INBOX", "SENT"], "sync_attachments": false}',
    NULL,  -- No actual credentials in dev seed data
    'paused',  -- Paused so it doesn't try to sync without credentials
    60,
    NOW(),
    NOW()
);

-- Demo Data Source (Slack)
INSERT INTO data_sources (
    id,
    tenant_id,
    source_type,
    name,
    config,
    credentials_encrypted,
    status,
    sync_frequency_minutes,
    created_at,
    updated_at
)
VALUES (
    '323e4567-e89b-12d3-a456-426614174101',
    '123e4567-e89b-12d3-a456-426614174000',
    'slack',
    'Demo Slack Workspace',
    '{"workspace": "demo-workspace", "channels": ["general", "engineering"]}',
    NULL,
    'paused',
    30,
    NOW(),
    NOW()
);

-- Demo Document (Email)
INSERT INTO documents (
    id,
    tenant_id,
    data_source_id,
    external_id,
    content_hash,
    title,
    content,
    content_type,
    source_url,
    source_metadata,
    processed_status,
    processed_at,
    word_count,
    language,
    created_at,
    updated_at
)
VALUES (
    '423e4567-e89b-12d3-a456-426614174200',
    '123e4567-e89b-12d3-a456-426614174000',
    '323e4567-e89b-12d3-a456-426614174100',
    'gmail-msg-demo-001',
    '5d41402abc4b2a76b9719d911017c592',  -- MD5 of "hello"
    'Welcome to ASWA Demo',
    'This is a demo email document for testing the ASWA platform. It contains sample content for testing document processing, chunking, and insight extraction.',
    'email',
    'https://mail.google.com/mail/u/0/#inbox/demo-001',
    '{"from": "demo@example.com", "to": ["admin@demo.aswa.com"], "subject": "Welcome to ASWA Demo", "date": "2024-01-15T10:00:00Z"}',
    'completed',
    NOW(),
    25,
    'en',
    NOW() - INTERVAL '7 days',
    NOW() - INTERVAL '7 days'
);

-- Demo Document (Slack Message)
INSERT INTO documents (
    id,
    tenant_id,
    data_source_id,
    external_id,
    content_hash,
    title,
    content,
    content_type,
    source_url,
    source_metadata,
    processed_status,
    word_count,
    language,
    created_at,
    updated_at
)
VALUES (
    '423e4567-e89b-12d3-a456-426614174201',
    '123e4567-e89b-12d3-a456-426614174000',
    '323e4567-e89b-12d3-a456-426614174101',
    'slack-msg-demo-001',
    '098f6bcd4621d373cade4e832627b4f6',  -- MD5 of "test"
    NULL,  -- Slack messages typically don't have titles
    'Hey team, the new feature deployment went smoothly. All systems are operational.',
    'message',
    'https://demo-workspace.slack.com/archives/C123/p1234567890',
    '{"channel": "engineering", "user": "demo-user", "timestamp": "1234567890.123456"}',
    'completed',
    12,
    'en',
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '3 days'
);

-- Demo Insight (Entity extraction)
INSERT INTO insights (
    id,
    tenant_id,
    insight_type,
    title,
    description,
    content,
    confidence,
    severity,
    category,
    tags,
    source_documents,
    evidence_snippets,
    status,
    created_at,
    updated_at
)
VALUES (
    '523e4567-e89b-12d3-a456-426614174300',
    '123e4567-e89b-12d3-a456-426614174000',
    'entity',
    'Product Deployment Detected',
    'System detected a successful product deployment mentioned in team communications',
    '{"entity_type": "event", "event_name": "feature_deployment", "status": "successful", "impact": "positive"}',
    0.92,
    'info',
    'Operations',
    ARRAY['deployment', 'success', 'engineering'],
    ARRAY['423e4567-e89b-12d3-a456-426614174201'],
    ARRAY['the new feature deployment went smoothly'],
    'active',
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '3 days'
);

-- Demo Alert Configuration
INSERT INTO alert_configs (
    id,
    tenant_id,
    created_by,
    name,
    description,
    pattern_query,
    conditions,
    notification_channels,
    frequency,
    status,
    created_at,
    updated_at
)
VALUES (
    '623e4567-e89b-12d3-a456-426614174400',
    '123e4567-e89b-12d3-a456-426614174000',
    '223e4567-e89b-12d3-a456-426614174001',  -- Demo Admin
    'High-Risk Insights',
    'Alert on any high or critical severity insights',
    '{"severity": ["high", "critical"], "status": "active"}',
    '{"min_confidence": 0.8}',
    '{"email": ["admin@demo.aswa.com"], "slack": ["#alerts"]}',
    'realtime',
    'active',
    NOW() - INTERVAL '10 days',
    NOW() - INTERVAL '10 days'
);

-- Demo API Key (for testing programmatic access)
-- Note: This is a demo key hash, not a real key
INSERT INTO api_keys (
    id,
    tenant_id,
    created_by,
    name,
    key_hash,
    key_prefix,
    scopes,
    rate_limit_per_hour,
    status,
    created_at
)
VALUES (
    '723e4567-e89b-12d3-a456-426614174500',
    '123e4567-e89b-12d3-a456-426614174000',
    '223e4567-e89b-12d3-a456-426614174001',
    'Demo API Key',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',  -- SHA-256 of empty string (demo only)
    'aswa_demo_',
    ARRAY['read:documents', 'read:insights', 'write:documents'],
    1000,
    'active',
    NOW() - INTERVAL '5 days'
);

-- Demo Sync Job
INSERT INTO sync_jobs (
    id,
    data_source_id,
    status,
    started_at,
    completed_at,
    documents_processed,
    documents_created,
    documents_updated,
    documents_skipped,
    metadata,
    created_at
)
VALUES (
    '823e4567-e89b-12d3-a456-426614174600',
    '323e4567-e89b-12d3-a456-426614174100',  -- Gmail data source
    'completed',
    NOW() - INTERVAL '7 days',
    NOW() - INTERVAL '7 days' + INTERVAL '5 minutes',
    10,
    8,
    2,
    0,
    '{"batch_size": 100, "sync_type": "incremental"}',
    NOW() - INTERVAL '7 days'
);

-- Demo Audit Log Entry
INSERT INTO audit_logs (
    tenant_id,
    user_id,
    action,
    resource_type,
    resource_id,
    new_values,
    request_id,
    created_at
)
VALUES (
    '123e4567-e89b-12d3-a456-426614174000',
    '223e4567-e89b-12d3-a456-426614174001',
    'CREATE',
    'data_source',
    '323e4567-e89b-12d3-a456-426614174100',
    '{"name": "Demo Gmail Account", "source_type": "gmail"}',
    'req-demo-001',
    NOW() - INTERVAL '10 days'
);

-- ============================================================================
-- VERIFICATION QUERIES (for development)
-- ============================================================================
-- Run these queries after migration to verify seed data loaded correctly:
--
-- SELECT COUNT(*) FROM tenants WHERE slug = 'demo';  -- Should return 1
-- SELECT COUNT(*) FROM users WHERE tenant_id = '123e4567-e89b-12d3-a456-426614174000';  -- Should return 3
-- SELECT COUNT(*) FROM data_sources WHERE tenant_id = '123e4567-e89b-12d3-a456-426614174000';  -- Should return 2
-- SELECT COUNT(*) FROM documents WHERE tenant_id = '123e4567-e89b-12d3-a456-426614174000';  -- Should return 2
-- ============================================================================

COMMENT ON TABLE users IS 'Demo seed data loaded successfully';
