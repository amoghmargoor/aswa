-- ASWA Initial Database Schema
-- Version: V001
-- Description: Creates core tables for tenants, users, data sources, documents, insights, and alerts

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

-- UUID generation functions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Trigram indexing for fuzzy text search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Tenants table: Multi-tenant organization accounts
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    settings JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE tenants IS 'Organization accounts with multi-tenant isolation';
COMMENT ON COLUMN tenants.slug IS 'URL-safe unique identifier for tenant';
COMMENT ON COLUMN tenants.settings IS 'Tenant-specific configuration and preferences';

-- Users table: User accounts scoped to tenants
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'manager', 'member', 'viewer')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'deleted')),
    settings JSONB NOT NULL DEFAULT '{}',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

COMMENT ON TABLE users IS 'User accounts with tenant isolation and role-based access';
COMMENT ON CONSTRAINT users_tenant_id_email_key ON users IS 'Ensures email uniqueness within tenant';

-- ============================================================================
-- DATA SOURCE MANAGEMENT
-- ============================================================================

-- Data Sources table: External data source configurations
CREATE TABLE data_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('gmail', 'outlook', 'slack', 'teams', 'gdrive', 'sharepoint', 'salesforce', 'zoho', 'confluence', 'notion', 'zoom', 'custom')),
    name VARCHAR(255) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    credentials_encrypted BYTEA,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'error', 'deleted')),
    last_sync_at TIMESTAMPTZ,
    sync_cursor TEXT,
    error_message TEXT,
    sync_frequency_minutes INT NOT NULL DEFAULT 60,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE data_sources IS 'External data source connections (email, chat, documents, etc.)';
COMMENT ON COLUMN data_sources.credentials_encrypted IS 'Encrypted OAuth tokens or API credentials';
COMMENT ON COLUMN data_sources.sync_cursor IS 'Pagination or incremental sync marker';

-- Documents table: Ingested content from data sources
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    data_source_id UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    external_id VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    title VARCHAR(1000),
    content TEXT,
    content_type VARCHAR(100) NOT NULL CHECK (content_type IN ('email', 'message', 'document', 'transcript', 'note', 'ticket')),
    source_url TEXT,
    source_metadata JSONB NOT NULL DEFAULT '{}',
    processed_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (processed_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
    processed_at TIMESTAMPTZ,
    error_message TEXT,
    word_count INT,
    language VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, data_source_id, external_id)
);

COMMENT ON TABLE documents IS 'Normalized documents from all data sources';
COMMENT ON COLUMN documents.content_hash IS 'SHA-256 hash for deduplication';
COMMENT ON COLUMN documents.external_id IS 'Source-specific unique identifier (e.g., Gmail message ID)';
COMMENT ON CONSTRAINT documents_tenant_id_data_source_id_external_id_key ON documents IS 'Prevents duplicate imports from same source';

-- Document Chunks table: Chunked documents for vector embedding
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    token_count INT NOT NULL,
    vector_id VARCHAR(100),
    start_char INT,
    end_char INT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

COMMENT ON TABLE document_chunks IS 'Document segments for vector embedding and retrieval';
COMMENT ON COLUMN document_chunks.vector_id IS 'Reference to vector in Pinecone or other vector DB';
COMMENT ON COLUMN document_chunks.token_count IS 'Approximate token count for LLM context planning';

-- ============================================================================
-- INSIGHTS AND ANALYSIS
-- ============================================================================

-- Insights table: AI-generated insights from documents
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    insight_type VARCHAR(50) NOT NULL CHECK (insight_type IN ('entity', 'risk', 'opportunity', 'pattern', 'relationship', 'trend', 'anomaly')),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    content JSONB NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    severity VARCHAR(50) CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    category VARCHAR(100),
    tags TEXT[] DEFAULT '{}',
    source_documents UUID[] NOT NULL,
    evidence_snippets TEXT[],
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'dismissed', 'resolved')),
    user_feedback VARCHAR(50) CHECK (user_feedback IN ('confirmed', 'rejected', 'modified')),
    feedback_by UUID REFERENCES users(id),
    feedback_comment TEXT,
    feedback_at TIMESTAMPTZ,
    vector_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE insights IS 'LLM-extracted insights with confidence scores and user feedback';
COMMENT ON COLUMN insights.content IS 'Structured insight data (entities, relationships, metrics, etc.)';
COMMENT ON COLUMN insights.source_documents IS 'Array of document IDs that contributed to this insight';

-- Entity Relationships table: Connections between insights
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_insight_id UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    target_insight_id UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,
    direction VARCHAR(20) NOT NULL DEFAULT 'directed' CHECK (direction IN ('directed', 'bidirectional')),
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_insight_id, target_insight_id, relationship_type)
);

COMMENT ON TABLE entity_relationships IS 'Graph of relationships between insights (e.g., person-works-at-company)';
COMMENT ON COLUMN entity_relationships.relationship_type IS 'Semantic relationship (e.g., "mentions", "works_at", "influences")';

-- ============================================================================
-- ALERTING AND NOTIFICATIONS
-- ============================================================================

-- Alert Configurations table: User-defined alert rules
CREATE TABLE alert_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    pattern_query TEXT NOT NULL,
    conditions JSONB NOT NULL DEFAULT '{}',
    notification_channels JSONB NOT NULL,
    frequency VARCHAR(50) NOT NULL DEFAULT 'realtime' CHECK (frequency IN ('realtime', 'hourly', 'daily', 'weekly')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'deleted')),
    last_triggered_at TIMESTAMPTZ,
    trigger_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE alert_configs IS 'User-defined alerting rules and notification preferences';
COMMENT ON COLUMN alert_configs.pattern_query IS 'Query or pattern to match against insights';
COMMENT ON COLUMN alert_configs.notification_channels IS 'JSON config for email, Slack, webhook, etc.';

-- Alert History table: Record of triggered alerts
CREATE TABLE alert_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_config_id UUID NOT NULL REFERENCES alert_configs(id) ON DELETE CASCADE,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    matched_insights UUID[] NOT NULL,
    notification_status JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE alert_history IS 'Audit trail of alert triggers and notification delivery';
COMMENT ON COLUMN alert_history.notification_status IS 'Delivery status for each notification channel';

-- ============================================================================
-- AUDIT AND ACCESS CONTROL
-- ============================================================================

-- Audit Logs table: Append-only audit trail
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE audit_logs IS 'Immutable audit log of all system actions';
COMMENT ON COLUMN audit_logs.old_values IS 'Snapshot of resource before change (for UPDATE/DELETE)';
COMMENT ON COLUMN audit_logs.new_values IS 'Snapshot of resource after change (for CREATE/UPDATE)';

-- API Keys table: Programmatic access credentials
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    key_prefix VARCHAR(10) NOT NULL,
    scopes TEXT[] NOT NULL,
    rate_limit_per_hour INT NOT NULL DEFAULT 1000,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE api_keys IS 'API keys for programmatic access with scopes and rate limits';
COMMENT ON COLUMN api_keys.key_hash IS 'SHA-256 hash of the API key (never store plaintext)';
COMMENT ON COLUMN api_keys.key_prefix IS 'First 8 chars of key for display (e.g., "aswa_dev_")';

-- ============================================================================
-- BACKGROUND JOBS
-- ============================================================================

-- Sync Jobs table: Tracks data source synchronization jobs
CREATE TABLE sync_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    data_source_id UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    documents_processed INT DEFAULT 0,
    documents_created INT DEFAULT 0,
    documents_updated INT DEFAULT 0,
    documents_skipped INT DEFAULT 0,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sync_jobs IS 'Background job tracking for data source ingestion';
COMMENT ON COLUMN sync_jobs.metadata IS 'Job-specific metadata (batch size, filters, etc.)';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Users indexes
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant_role ON users(tenant_id, role);

-- Data Sources indexes
CREATE INDEX idx_data_sources_tenant ON data_sources(tenant_id);
CREATE INDEX idx_data_sources_tenant_type ON data_sources(tenant_id, source_type);
CREATE INDEX idx_data_sources_status ON data_sources(status) WHERE status = 'active';

-- Documents indexes
CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_source ON documents(data_source_id);
CREATE INDEX idx_documents_status ON documents(processed_status);
CREATE INDEX idx_documents_tenant_hash ON documents(tenant_id, content_hash);
CREATE INDEX idx_documents_tenant_created ON documents(tenant_id, created_at DESC);

-- Full-text search index for documents (uses pg_trgm)
CREATE INDEX idx_documents_content_fts ON documents
    USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')));

-- Document Chunks indexes
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_vector ON document_chunks(vector_id) WHERE vector_id IS NOT NULL;

-- Insights indexes
CREATE INDEX idx_insights_tenant ON insights(tenant_id);
CREATE INDEX idx_insights_tenant_type ON insights(tenant_id, insight_type);
CREATE INDEX idx_insights_tenant_created ON insights(tenant_id, created_at DESC);
CREATE INDEX idx_insights_status ON insights(status) WHERE status = 'active';

-- Full-text search index for insights
CREATE INDEX idx_insights_content_fts ON insights
    USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));

-- Entity Relationships indexes
CREATE INDEX idx_relationships_source ON entity_relationships(source_insight_id);
CREATE INDEX idx_relationships_target ON entity_relationships(target_insight_id);

-- Alert Configs indexes
CREATE INDEX idx_alerts_tenant ON alert_configs(tenant_id);
CREATE INDEX idx_alerts_status ON alert_configs(status) WHERE status = 'active';

-- Alert History indexes
CREATE INDEX idx_alert_history_config ON alert_history(alert_config_id);
CREATE INDEX idx_alert_history_time ON alert_history(triggered_at DESC);

-- Audit Logs indexes (optimized for common queries)
CREATE INDEX idx_audit_tenant_time ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id) WHERE user_id IS NOT NULL;

-- API Keys indexes
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);

-- Sync Jobs indexes
CREATE INDEX idx_sync_jobs_source ON sync_jobs(data_source_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Function to automatically update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

COMMENT ON FUNCTION update_updated_at_column() IS 'Automatically sets updated_at to current timestamp on UPDATE';

-- Apply updated_at triggers to all tables with updated_at column
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_data_sources_updated_at
    BEFORE UPDATE ON data_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_insights_updated_at
    BEFORE UPDATE ON insights
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alert_configs_updated_at
    BEFORE UPDATE ON alert_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SCHEMA VERSION
-- ============================================================================

COMMENT ON SCHEMA public IS 'ASWA Database Schema v1.0 - Initial schema with multi-tenant support';
