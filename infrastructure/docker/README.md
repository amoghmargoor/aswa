# ASWA Docker Configuration

Docker-based local development environment for the ASWA platform.

## Directory Structure

```
infrastructure/docker/
├── api-gateway/          # Java Spring Boot API Gateway
│   └── Dockerfile
├── python-base/          # Python base image for ML services
│   └── Dockerfile
├── postgres/             # PostgreSQL with initialization
│   ├── Dockerfile
│   └── init.sql
└── pgadmin/              # PgAdmin configuration
    └── servers.json
```

## Services

### Core Services (Always Running)
- **PostgreSQL 16**: Primary database with pg_trgm extension
- **Redis 7**: Cache and message broker

### Application Services (Optional - Profile: `services`)
- **API Gateway**: Java Spring Boot REST API on port 8080

### Management Tools (Optional - Profile: `tools`)
- **PgAdmin**: Database management UI on port 5050
- **Redis Commander**: Redis management UI on port 8081

## Quick Start

### 1. Start Core Services Only
```bash
docker-compose up -d
```

This starts PostgreSQL and Redis.

### 2. Start with API Gateway
```bash
docker-compose --profile services up -d
```

### 3. Start Everything (Including Management Tools)
```bash
docker-compose --profile services --profile tools up -d
```

### 4. Use the Development Script
```bash
# Start all services
./scripts/dev.sh start all

# Show status
./scripts/dev.sh status

# View logs
./scripts/dev.sh logs api-gateway

# Stop everything
./scripts/dev.sh stop
```

## Accessing Services

### PostgreSQL
```bash
psql -h localhost -U aswa -d aswa
# Password: aswa_dev_password
```

### Redis
```bash
redis-cli -h localhost -p 6379 -a aswa_dev_password
```

### API Gateway
- Base URL: http://localhost:8080
- Health: http://localhost:8080/health
- Swagger UI: http://localhost:8080/swagger-ui.html
- API Docs: http://localhost:8080/v3/api-docs

### PgAdmin
- URL: http://localhost:5050
- Email: admin@aswa.local
- Password: admin

### Redis Commander
- URL: http://localhost:8081

## Building Images

### Build All Images
```bash
docker-compose build
```

### Build Specific Service
```bash
docker-compose build api-gateway
```

### Rebuild and Restart
```bash
docker-compose up -d --build api-gateway
```

## Database Migrations

Run Flyway migrations:
```bash
./scripts/db-migrate.sh migrate dev
```

## Logs

### View All Logs
```bash
docker-compose logs -f
```

### View Specific Service
```bash
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f api-gateway
```

## Cleaning Up

### Stop Services (Keep Data)
```bash
docker-compose down
```

### Stop and Remove All Data
```bash
docker-compose down -v
```
**WARNING**: This deletes all database data and volumes!

## Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Key variables:
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`: PostgreSQL credentials
- `REDIS_PASSWORD`: Redis password
- `JWT_SECRET`: JWT signing key (min 32 characters)
- `API_GATEWAY_PORT`: API Gateway port (default: 8080)

## Troubleshooting

### Services Won't Start
```bash
# Check Docker is running
docker ps

# Check logs for errors
docker-compose logs

# Ensure ports aren't already in use
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :8080  # API Gateway
```

### Database Connection Issues
```bash
# Check PostgreSQL is healthy
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Test connection
psql -h localhost -U aswa -d aswa
```

### API Gateway Build Fails
```bash
# Clean Gradle cache
./gradlew clean

# Rebuild from scratch
docker-compose build --no-cache api-gateway
```

### Out of Disk Space
```bash
# Remove unused Docker images
docker image prune -a

# Remove all stopped containers
docker container prune

# Remove unused volumes
docker volume prune
```

## Performance Tips

### MacOS/Windows
For better performance on non-Linux systems:

1. **Increase Docker Resources**
   - Docker Desktop → Settings → Resources
   - RAM: 4GB+ recommended
   - CPUs: 4+ recommended

2. **Use Docker Volumes** (Not Bind Mounts)
   - Already configured in docker-compose.yml

3. **Enable VirtioFS** (MacOS)
   - Docker Desktop → Settings → General
   - Enable "VirtioFS" for file sharing

## Security Notes

### Development vs Production
- **Development**: Uses weak passwords and exposes ports
- **Production**: Must use:
  - Strong, unique passwords
  - Secrets management (AWS Secrets Manager, etc.)
  - Private networks
  - TLS/SSL certificates
  - Limited port exposure

### Credentials
Never commit:
- `.env` file (already in .gitignore)
- Any files with real API keys or passwords
- Production database dumps

## Next Steps

After starting the services:

1. **Run Migrations**
   ```bash
   ./scripts/db-migrate.sh migrate dev
   ```

2. **Verify API Gateway**
   ```bash
   curl http://localhost:8080/health
   ```

3. **Access Swagger UI**
   Open http://localhost:8080/swagger-ui.html

4. **Create Test User** (via API or SQL)

5. **Start Development**

## Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Docker Image](https://hub.docker.com/_/postgres)
- [Redis Docker Image](https://hub.docker.com/_/redis)
- [Spring Boot Docker Guide](https://spring.io/guides/gs/spring-boot-docker/)
