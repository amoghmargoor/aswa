# ASWA Docker & Local Development Setup - Complete

## Summary

Task 1.4.1: Docker Configuration has been completed successfully. The ASWA platform now has a comprehensive Docker-based local development environment.

## What Was Created

### 1. Dockerfiles

#### API Gateway Dockerfile
**Location**: `infrastructure/docker/api-gateway/Dockerfile`
- Multi-stage build for Java Spring Boot application
- Base: Eclipse Temurin 21 (JDK for build, JRE for runtime)
- Non-root user execution for security
- JVM tuning for containerized environments
- Health check endpoint integration
- Optimized layer caching

#### Python Base Dockerfile
**Location**: `infrastructure/docker/python-base/Dockerfile`
- Base image for Python ML services (Python 3.11)
- Poetry for dependency management
- Multi-stage build (builder + runtime)
- System dependencies for PostgreSQL
- Non-root user execution
- Virtual environment in /app/.venv

#### PostgreSQL Dockerfile
**Location**: `infrastructure/docker/postgres/Dockerfile`
- PostgreSQL 16 with alpine base
- Custom initialization scripts
- pg_trgm extension for full-text search
- Health check with pg_isready

### 2. Docker Compose Configuration

**Location**: `docker-compose.yml`

#### Services Configured:
1. **PostgreSQL** (Always running)
   - Port: 5432
   - Volume: postgres_data
   - Health checks enabled
   - Automatic migration script loading

2. **Redis** (Always running)
   - Port: 6379
   - Volume: redis_data
   - AOF persistence enabled
   - Password protected

3. **API Gateway** (Profile: `services`)
   - Port: 8080
   - Depends on PostgreSQL + Redis
   - Environment variable configuration
   - Health check on /health endpoint
   - Logs to ./logs/api-gateway

4. **PgAdmin** (Profile: `tools`)
   - Port: 5050
   - Pre-configured server connection
   - Volume: pgadmin_data

5. **Redis Commander** (Profile: `tools`)
   - Port: 8081
   - Pre-configured Redis connection

#### Features:
- Profile-based service grouping (core, services, tools)
- Health checks on all critical services
- Named volumes for data persistence
- Dedicated network (aswa-network)
- Automatic service dependencies
- Restart policies

### 3. Environment Configuration

#### .env File
**Location**: `.env`
- Development-ready default values
- Database credentials
- Redis configuration
- JWT secrets
- Port mappings

#### PgAdmin Configuration
**Location**: `infrastructure/docker/pgadmin/servers.json`
- Pre-configured connection to local PostgreSQL
- Automatic login configuration

### 4. Development Scripts

#### Development Manager Script
**Location**: `scripts/dev.sh`

Commands:
```bash
./scripts/dev.sh start [profile]  # Start services
./scripts/dev.sh stop             # Stop services
./scripts/dev.sh restart          # Restart services
./scripts/dev.sh status           # Show status
./scripts/dev.sh logs [service]   # View logs
./scripts/dev.sh build [service]  # Build images
./scripts/dev.sh migrate          # Run migrations
./scripts/dev.sh clean            # Clean all data
./scripts/dev.sh info             # Show connection info
```

Features:
- Colored output for readability
- Prerequisites checking
- Service health monitoring
- Connection information display
- Safe data cleanup with confirmation

### 5. Makefile Targets

**Enhanced Makefile** with Docker commands:

```bash
make dev-up          # Start core services (postgres, redis)
make dev-services    # Start with API Gateway
make dev-tools       # Start with management tools
make dev-all         # Start everything
make dev-down        # Stop all services
make dev-restart     # Restart services
make dev-logs        # Show logs
make dev-status      # Show service status
make dev-clean       # Clean all data (with confirmation)
make db-shell        # Open PostgreSQL shell
make redis-shell     # Open Redis CLI
make db-migrate      # Run database migrations
```

### 6. Documentation

#### Docker README
**Location**: `infrastructure/docker/README.md`

Comprehensive guide covering:
- Directory structure
- Service descriptions
- Quick start guide
- Accessing services
- Building images
- Database migrations
- Logs and troubleshooting
- Performance tips
- Security notes

## Usage Examples

### Basic Development Workflow

1. **Start Core Services**
   ```bash
   make dev-up
   # or
   docker-compose up -d
   ```

2. **Run Database Migrations**
   ```bash
   make db-migrate
   ```

3. **Start API Gateway**
   ```bash
   make dev-services
   # or
   docker-compose --profile services up -d
   ```

4. **Access Services**
   - API: http://localhost:8080
   - Swagger: http://localhost:8080/swagger-ui.html
   - Health: http://localhost:8080/health

5. **View Logs**
   ```bash
   make dev-logs
   # or specific service
   docker-compose logs -f api-gateway
   ```

6. **Stop Everything**
   ```bash
   make dev-down
   ```

### With Management Tools

```bash
# Start everything
make dev-all

# Access tools
# PgAdmin: http://localhost:5050
# Redis Commander: http://localhost:8081
```

### Database Access

```bash
# PostgreSQL shell
make db-shell

# Or manually
psql -h localhost -U aswa -d aswa
# Password: aswa_dev_password

# Redis CLI
make redis-shell

# Or manually
redis-cli -h localhost -p 6379 -a aswa_dev_password
```

## Service Architecture

```
┌─────────────────────────────────────────────────┐
│                   Docker Host                    │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │ PostgreSQL │  │   Redis    │  │    API    │ │
│  │   :5432    │  │   :6379    │  │  Gateway  │ │
│  │            │  │            │  │   :8080   │ │
│  └────────────┘  └────────────┘  └───────────┘ │
│         │               │              │        │
│         └───────────────┴──────────────┘        │
│                   aswa-network                   │
│                                                  │
│  ┌────────────┐          ┌──────────────────┐  │
│  │  PgAdmin   │          │ Redis Commander  │  │
│  │   :5050    │          │      :8081       │  │
│  └────────────┘          └──────────────────┘  │
│                                                  │
└─────────────────────────────────────────────────┘
```

## Key Features

### 1. Multi-Stage Builds
- Smaller final images
- Faster builds with layer caching
- Separation of build and runtime dependencies

### 2. Security
- Non-root user execution
- Minimal base images (alpine)
- No hardcoded secrets in images
- Environment variable configuration

### 3. Development Experience
- Fast startup with profiles
- Hot reload support (when configured)
- Comprehensive logging
- Easy database access
- Management UIs included

### 4. Data Persistence
- Named volumes for data
- Separate volumes per service
- Easy backup/restore
- Clean separation from code

### 5. Health Monitoring
- Health checks on all services
- Automatic restart on failure
- Dependency ordering
- Readiness probes

## Port Mappings

| Service         | Port | URL                                    |
|----------------|------|----------------------------------------|
| PostgreSQL     | 5432 | localhost:5432                         |
| Redis          | 6379 | localhost:6379                         |
| API Gateway    | 8080 | http://localhost:8080                  |
| PgAdmin        | 5050 | http://localhost:5050                  |
| Redis Commander| 8081 | http://localhost:8081                  |

## Volume Mappings

| Volume              | Purpose                    |
|--------------------|----------------------------|
| postgres_data      | PostgreSQL database files  |
| redis_data         | Redis persistence (AOF)    |
| pgadmin_data       | PgAdmin configuration      |
| ./logs/api-gateway | API Gateway application logs|

## Network Configuration

- **Network Name**: aswa-network
- **Driver**: bridge
- **Purpose**: Isolated communication between services
- **DNS**: Automatic service name resolution

## Environment Variables

Key variables in `.env`:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aswa
DB_USER=aswa
DB_PASSWORD=aswa_dev_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=aswa_dev_password

# JWT
JWT_SECRET=dev-secret-key-must-be-at-least-32-characters-long-for-hs256
JWT_EXPIRATION=3600
JWT_REFRESH_EXPIRATION=604800

# Ports
API_GATEWAY_PORT=8080
PGADMIN_PORT=5050
REDIS_COMMANDER_PORT=8081
```

## Next Steps

1. **Run Migrations**
   ```bash
   ./scripts/db-migrate.sh migrate dev
   ```

2. **Verify Setup**
   ```bash
   # Check all services are running
   make dev-status

   # Test API Gateway
   curl http://localhost:8080/health
   ```

3. **Start Development**
   - API Gateway is ready at http://localhost:8080
   - Swagger UI at http://localhost:8080/swagger-ui.html
   - Database accessible via PgAdmin or CLI

4. **Add Python Services** (Future tasks)
   - Ingestion service
   - Insight engine
   - Query service

## Troubleshooting

### Services Won't Start
```bash
# Check Docker is running
docker ps

# Check for port conflicts
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :8080  # API Gateway

# View logs
docker-compose logs
```

### Build Failures
```bash
# Clean and rebuild
make clean
docker-compose build --no-cache

# Check Docker resources (MacOS/Windows)
# Docker Desktop → Settings → Resources
```

### Database Connection Issues
```bash
# Check PostgreSQL health
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Test connection
psql -h localhost -U aswa -d aswa
```

## Performance Tips

### For MacOS/Windows

1. **Increase Docker Resources**
   - RAM: 4GB+ recommended
   - CPUs: 4+ recommended

2. **Use Docker Volumes** (Already configured)
   - Faster than bind mounts
   - Better for databases

3. **Enable VirtioFS** (MacOS M1/M2)
   - Docker Desktop → Settings → General
   - Experimental file sharing

## Security Considerations

⚠️ **Development Only**: Current configuration uses:
- Weak passwords
- Exposed ports
- No TLS/SSL
- Permissive CORS

🔒 **Production Must Have**:
- Strong, unique passwords
- Secrets management (AWS Secrets Manager, Vault)
- Private networks
- TLS certificates
- Restricted CORS
- Network policies

## Files Created

```
infrastructure/docker/
├── api-gateway/
│   └── Dockerfile                  # Java Spring Boot service
├── python-base/
│   └── Dockerfile                  # Python ML services base
├── postgres/
│   ├── Dockerfile                  # PostgreSQL 16
│   └── init.sql                    # Initialization script
├── pgadmin/
│   └── servers.json                # PgAdmin server config
└── README.md                       # Documentation

docker-compose.yml                  # Main compose configuration
.env                                # Environment variables
scripts/dev.sh                      # Development manager script
Makefile                            # Enhanced with Docker targets
```

## Conclusion

The Docker configuration is complete and provides:
✅ Multi-service orchestration
✅ Profile-based service grouping
✅ Health monitoring
✅ Data persistence
✅ Management tools
✅ Development scripts
✅ Comprehensive documentation

The development environment is ready for:
- Local development
- Testing
- Database experimentation
- API development
- Integration work

**Next Phase**: Can proceed with Python service implementation (ingestion, ML processing, etc.)
