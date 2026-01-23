# ASWA Database Migrations

This directory contains Flyway database migrations for the ASWA platform.

## Overview

The database schema supports a multi-tenant SaaS architecture with the following core entities:

- **Tenants**: Organization accounts with isolated data
- **Users**: User accounts with role-based access control
- **Data Sources**: External integrations (Gmail, Slack, etc.)
- **Documents**: Ingested content from data sources
- **Document Chunks**: Segmented documents for vector embedding
- **Insights**: AI-generated insights and patterns
- **Entity Relationships**: Connections between insights
- **Alerts**: User-defined alerting rules
- **Audit Logs**: Immutable audit trail

## Migration Files

### V001__initial_schema.sql

Creates the complete database schema including:
- Core tables with proper constraints and foreign keys
- Indexes for query performance
- Full-text search indexes using PostgreSQL's GIN
- Triggers for automatic timestamp updates
- Comments documenting schema design decisions

**Tables Created:**
- `tenants` - Multi-tenant organizations
- `users` - User accounts with RBAC
- `data_sources` - External data source connections
- `documents` - Normalized documents from all sources
- `document_chunks` - Chunked documents for vector search
- `insights` - AI-extracted insights
- `entity_relationships` - Graph of insight relationships
- `alert_configs` - Alert rule configurations
- `alert_history` - Alert trigger audit trail
- `audit_logs` - System-wide audit log
- `api_keys` - Programmatic access credentials
- `sync_jobs` - Background job tracking

### V002__seed_dev_data.sql

Seeds development data for testing:
- Demo tenant (slug: "demo")
- Demo users (admin, manager, member)
- Sample data sources (Gmail, Slack)
- Sample documents and insights
- Sample alert configuration

**WARNING**: This migration should ONLY run in development environments.

## Running Migrations

### Prerequisites

1. PostgreSQL 16+ running (or use Docker Compose)
2. Flyway CLI installed (or script will auto-install)

### Using Docker Compose

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Wait for health check
docker-compose ps postgres

# Run migrations
./scripts/db-migrate.sh migrate dev
```

### Manual Setup

```bash
# Install Flyway (if not installed)
# Script will auto-download if needed

# Run migrations
./scripts/db-migrate.sh migrate dev
```

### Migration Commands

```bash
# Migrate to latest version
./scripts/db-migrate.sh migrate dev

# Show migration status
./scripts/db-migrate.sh info dev

# Validate migrations
./scripts/db-migrate.sh validate dev

# Repair schema history (if needed)
./scripts/db-migrate.sh repair dev

# Clean database (DEV ONLY - drops all objects!)
./scripts/db-migrate.sh clean dev
```

### Environment-Specific Migrations

```bash
# Development
./scripts/db-migrate.sh migrate dev

# Test
DB_HOST=test-db.example.com DB_PASSWORD=secret ./scripts/db-migrate.sh migrate test

# Production (requires confirmation)
DB_HOST=prod-db.example.com DB_PASSWORD=secret ./scripts/db-migrate.sh migrate prod
```

## Database Schema Design

### Multi-Tenancy

All core tables include a `tenant_id` column for data isolation. Key design decisions:

- **Row-level isolation**: Each tenant's data is isolated by tenant_id
- **Indexes**: All queries include tenant_id in WHERE clauses
- **Foreign keys**: Cascade deletes ensure referential integrity
- **Unique constraints**: Composite keys include tenant_id where appropriate

### Timestamps

All tables include:
- `created_at`: Immutable creation timestamp
- `updated_at`: Auto-updated via trigger on UPDATE

### Soft Deletes

Most tables use `status` enum instead of hard deletes:
- Tenants: `active`, `suspended`, `deleted`
- Users: `active`, `inactive`, `deleted`
- Data Sources: `active`, `paused`, `error`, `deleted`

### Audit Trail

The `audit_logs` table tracks all system actions:
- Append-only (no UPDATEs or DELETEs)
- Includes before/after snapshots for changes
- Indexed for tenant + time range queries

## Performance Considerations

### Indexes

Carefully designed indexes support common query patterns:

1. **Single-column indexes**: For foreign keys and status fields
2. **Composite indexes**: For multi-column WHERE clauses
3. **Partial indexes**: For active records only (WHERE status = 'active')
4. **GIN indexes**: For full-text search and JSONB queries

### Full-Text Search

Documents and insights support full-text search via:
```sql
CREATE INDEX idx_documents_content_fts ON documents
    USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')));
```

Query example:
```sql
SELECT * FROM documents
WHERE to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
    @@ to_tsquery('english', 'search & query');
```

### JSONB Columns

JSONB columns support flexible schemas:
- `settings` - Tenant/user preferences
- `config` - Data source configuration
- `content` - Insight structured data
- `metadata` - Additional context

Query JSONB:
```sql
-- Exact match
SELECT * FROM tenants WHERE settings->>'theme' = 'dark';

-- Containment
SELECT * FROM insights WHERE content @> '{"entity_type": "person"}';
```

## Extending the Schema

### Adding New Migrations

1. Create new migration file: `V003__description.sql`
2. Follow naming convention: `V{version}__{description}.sql`
3. Test in dev environment first
4. Run validation: `./scripts/db-migrate.sh validate dev`
5. Apply: `./scripts/db-migrate.sh migrate dev`

### Best Practices

1. **Never modify existing migrations** - Always create new ones
2. **Include comments** - Document complex logic and design decisions
3. **Use transactions** - Flyway wraps each migration in a transaction
4. **Test rollback** - Ensure data can be recovered if needed
5. **Version control** - All migrations must be in git

## Troubleshooting

### Migration Fails

```bash
# Check migration status
./scripts/db-migrate.sh info dev

# Repair schema history if needed
./scripts/db-migrate.sh repair dev

# For development, can clean and reapply
./scripts/db-migrate.sh clean dev
./scripts/db-migrate.sh migrate dev
```

### Connection Issues

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check connection manually
psql -h localhost -U aswa -d aswa

# Check environment variables
echo $DB_HOST $DB_PORT $DB_NAME
```

### Performance Issues

```bash
# Connect to database
psql -h localhost -U aswa -d aswa

# Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

# Analyze table statistics
ANALYZE documents;

# Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

## Production Deployment

### Pre-Deployment Checklist

- [ ] Test migrations in staging environment
- [ ] Backup production database
- [ ] Schedule maintenance window
- [ ] Verify migration files are in version control
- [ ] Review migration logs for errors
- [ ] Have rollback plan ready

### Deployment Process

1. **Backup database**
   ```bash
   pg_dump -h prod-db -U aswa -d aswa > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Run migrations**
   ```bash
   DB_HOST=prod-db DB_PASSWORD=$PROD_PASSWORD ./scripts/db-migrate.sh migrate prod
   ```

3. **Verify**
   ```bash
   DB_HOST=prod-db DB_PASSWORD=$PROD_PASSWORD ./scripts/db-migrate.sh info prod
   ```

### Rollback

If migration fails:
```bash
# Restore from backup
psql -h prod-db -U aswa -d aswa < backup_YYYYMMDD_HHMMSS.sql
```

## Security

- **Never commit passwords** - Use environment variables
- **Encrypt credentials** - Use Vault or similar for production
- **Limit permissions** - Use principle of least privilege
- **Audit access** - Monitor database connection logs
- **Encrypt at rest** - Enable PostgreSQL encryption

## Resources

- [Flyway Documentation](https://flywaydb.org/documentation/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [ASWA Architecture Documentation](../ArchitectureAndDesign.md)
