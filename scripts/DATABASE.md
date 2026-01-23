# ASWA Database Quick Reference

## Starting the Database

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f postgres
```

## Running Migrations

```bash
# First time setup
docker-compose up -d postgres
./scripts/db-migrate.sh migrate dev

# Check migration status
./scripts/db-migrate.sh info dev

# Validate migrations
./scripts/db-migrate.sh validate dev
```

## Connecting to Database

```bash
# Using psql command line
psql -h localhost -U aswa -d aswa
# Password: aswa_dev_password

# Or using Docker
docker-compose exec postgres psql -U aswa -d aswa
```

## Common SQL Queries

```sql
-- List all tenants
SELECT id, name, slug, status FROM tenants;

-- List users for a tenant
SELECT id, email, name, role FROM users
WHERE tenant_id = '123e4567-e89b-12d3-a456-426614174000';

-- Check document count by tenant
SELECT tenant_id, COUNT(*) as doc_count
FROM documents
GROUP BY tenant_id;

-- View recent insights
SELECT id, insight_type, title, confidence, created_at
FROM insights
WHERE tenant_id = '123e4567-e89b-12d3-a456-426614174000'
ORDER BY created_at DESC
LIMIT 10;

-- Check sync job status
SELECT id, status, started_at, completed_at,
       documents_processed, documents_created
FROM sync_jobs
ORDER BY created_at DESC
LIMIT 10;
```

## Database Management

```bash
# Backup database
docker-compose exec postgres pg_dump -U aswa -d aswa > backup_$(date +%Y%m%d).sql

# Restore database
docker-compose exec -T postgres psql -U aswa -d aswa < backup_20240101.sql

# Reset database (DEV ONLY!)
./scripts/db-migrate.sh clean dev
./scripts/db-migrate.sh migrate dev

# Stop database
docker-compose stop postgres

# Remove all data (WARNING!)
docker-compose down -v
```

## Management UI

```bash
# Start with management tools
docker-compose --profile tools up -d

# Access PgAdmin
open http://localhost:5050
# Email: admin@aswa.local
# Password: admin

# Access Redis Commander
open http://localhost:8081
```

## Troubleshooting

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View recent logs
docker-compose logs --tail=100 postgres

# Restart PostgreSQL
docker-compose restart postgres

# Connect to PostgreSQL container
docker-compose exec postgres bash

# Check PostgreSQL configuration
docker-compose exec postgres cat /var/lib/postgresql/data/postgresql.conf
```

## Environment Variables

```bash
# Development (default)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=aswa
export DB_USER=aswa
export DB_PASSWORD=aswa_dev_password

# Test environment
export DB_HOST=test-db.example.com
export DB_PASSWORD=test_password
./scripts/db-migrate.sh migrate test

# Production environment
export DB_HOST=prod-db.example.com
export DB_PASSWORD=$PROD_DB_PASSWORD
./scripts/db-migrate.sh migrate prod
```

## Performance Monitoring

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('aswa'));

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
LIMIT 20;

-- Check slow queries (requires pg_stat_statements extension)
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;

-- Check active connections
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    LEFT(query, 50) as query
FROM pg_stat_activity
WHERE datname = 'aswa';
```

## Security Best Practices

1. **Never commit passwords** - Use environment variables or secrets manager
2. **Rotate credentials** - Change database passwords regularly
3. **Limit access** - Use firewall rules to restrict database access
4. **Enable SSL** - Use encrypted connections in production
5. **Monitor access** - Review audit logs regularly
6. **Backup regularly** - Automate database backups
7. **Test restores** - Verify backups can be restored

## Next Steps

- [ ] Run initial migrations: `./scripts/db-migrate.sh migrate dev`
- [ ] Verify seed data: `psql -h localhost -U aswa -d aswa -c "SELECT * FROM tenants;"`
- [ ] Configure application to connect to database
- [ ] Set up automated backups
- [ ] Configure monitoring and alerting
