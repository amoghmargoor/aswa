# ASWA Developer Guide

A quick-start guide for running ASWA on your Mac laptop for local development.

---

## Quick Start (TL;DR)

```bash
# 1. Clone and setup
git clone <repo-url> && cd aswa
./scripts/dev.sh setup

# 2. Add your API keys to .env
vi infrastructure/docker/.env

# 3. Start everything
./scripts/dev.sh up

# 4. Open in browser
open http://localhost:3000
```

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Quick Start](#quick-start)
4. [Running Options](#running-options)
5. [Service-by-Service Guide](#service-by-service-guide)
6. [Common Tasks](#common-tasks)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Software | Version | Install Command |
|----------|---------|-----------------|
| Docker Desktop | 4.x+ | [Download](https://www.docker.com/products/docker-desktop/) |
| Git | 2.x+ | `brew install git` |

### Optional (for native development)

| Software | Version | Install Command |
|----------|---------|-----------------|
| Python | 3.11+ | `brew install python@3.11` |
| Node.js | 20+ | `brew install node@20` |
| Java | 21+ | `brew install openjdk@21` |
| Poetry | 1.7+ | `pip install poetry` |

---

## System Requirements

### Minimum (Lightweight Mode)
```
┌─────────────────────────────────────┐
│  MINIMUM REQUIREMENTS               │
├─────────────────────────────────────┤
│  CPU:     4 cores                   │
│  RAM:     8 GB                      │
│  Disk:    20 GB free                │
│  Docker:  4 GB RAM allocated        │
└─────────────────────────────────────┘

Runs: PostgreSQL, Redis, 1-2 services
```

### Recommended (Full Stack)
```
┌─────────────────────────────────────┐
│  RECOMMENDED REQUIREMENTS           │
├─────────────────────────────────────┤
│  CPU:     8 cores (M1/M2/M3 ideal)  │
│  RAM:     16 GB                     │
│  Disk:    50 GB free                │
│  Docker:  8-10 GB RAM allocated     │
└─────────────────────────────────────┘

Runs: Full stack with all services
```

### Docker Desktop Settings

1. Open Docker Desktop → Settings → Resources
2. Configure:
   - **CPUs**: 4-6 (leave 2 for macOS)
   - **Memory**: 8-10 GB
   - **Swap**: 2 GB
   - **Disk**: 50 GB+

```
┌─────────────────────────────────────────────────────────────┐
│  Docker Desktop → Settings → Resources                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  CPUs          [====|====|====|====|    |    ]  4 / 8       │
│  Memory        [========|========|      ]       8.00 GB      │
│  Swap          [====|               ]           2.00 GB      │
│  Virtual Disk  [==========|         ]          50 GB         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Step 1: Clone Repository

```bash
git clone <your-repo-url>
cd aswa
```

### Step 2: Run Setup

```bash
./scripts/dev.sh setup
```

This will:
- Check prerequisites
- Create `.env` file from template
- Install Python dependencies
- Install Node.js dependencies
- Build Java projects

### Step 3: Configure Environment

```bash
# Edit the .env file
vi infrastructure/docker/.env
```

**Required API Keys:**
```bash
# At minimum, set one LLM provider:
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 4: Start Services

```bash
# Start full stack
./scripts/dev.sh up

# Or build and start (first time)
./scripts/dev.sh up --build
```

### Step 5: Verify

```bash
# Check status
./scripts/dev.sh status

# View logs
./scripts/dev.sh logs
```

### Step 6: Access

| Service | URL |
|---------|-----|
| Web Dashboard | http://localhost:3000 |
| API Gateway | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Jaeger (Tracing) | http://localhost:16686 |
| MinIO Console | http://localhost:9001 |
| Mailpit (Email) | http://localhost:8025 |

---

## Running Options

### Option 1: Full Stack (Recommended)

Runs all services via Docker. Best for integration testing.

```bash
./scripts/dev.sh up
```

**Services Started:**
```
┌────────────────────────────────────────────────────────────────┐
│                    FULL STACK MODE                              │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Web UI    │  │ API Gateway │  │  Ingestion  │            │
│  │   :3000     │  │   :8000     │  │   :8001     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Query     │  │   Insight   │  │    Agent    │            │
│  │   :8002     │  │   :8003     │  │   :8090     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ PostgreSQL  │  │   Redis     │  │Elasticsearch│            │
│  │   :5432     │  │   :6379     │  │   :9200     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐                              │
│  │   MinIO     │  │   Jaeger    │                              │
│  │   :9000     │  │  :16686     │                              │
│  └─────────────┘  └─────────────┘                              │
│                                                                 │
│  Memory Usage: ~6-8 GB                                          │
└────────────────────────────────────────────────────────────────┘
```

### Option 2: Lightweight Mode

Run only databases in Docker, services natively. Best for active development.

```bash
# Start only infrastructure
docker-compose up -d postgres redis

# Run services natively (in separate terminals)

# Terminal 1: API Gateway
cd services/api-gateway
./gradlew bootRun

# Terminal 2: Ingestion Service
cd services/ingestion-service
poetry run uvicorn aswa_ingestion.main:app --reload --port 8001

# Terminal 3: Query Service
cd services/query-service
poetry run uvicorn aswa_query.main:app --reload --port 8002

# Terminal 4: Web Dashboard
cd services/web-dashboard
npm run dev
```

**Memory Usage: ~2-3 GB**

### Option 3: Minimal Mode

Run the absolute minimum for specific feature work.

```bash
# Just database
docker-compose up -d postgres redis

# Single service you're working on
cd services/ingestion-service
poetry run uvicorn aswa_ingestion.main:app --reload --port 8001
```

**Memory Usage: ~1 GB**

---

## Service-by-Service Guide

### API Gateway (Java Spring Boot)

```bash
# Location
cd services/api-gateway

# Run with Gradle
./gradlew bootRun

# Run with debug
./gradlew bootRun --debug-jvm

# Run tests
./gradlew test

# Build JAR
./gradlew build
```

**Environment Variables:**
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=aswa
export DB_USER=aswa
export DB_PASSWORD=aswa_dev_password
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

### Ingestion Service (Python FastAPI)

```bash
# Location
cd services/ingestion-service

# Install dependencies
poetry install

# Run with auto-reload
poetry run uvicorn aswa_ingestion.main:app --reload --port 8001

# Run with debugger
poetry run python -m debugpy --listen 5678 -m uvicorn aswa_ingestion.main:app --port 8001

# Run tests
poetry run pytest tests/ -v

# Run with coverage
poetry run pytest tests/ --cov=src --cov-report=html
```

**Environment Variables:**
```bash
export DATABASE_URL=postgresql+asyncpg://aswa:aswa@localhost:5432/aswa
export REDIS_URL=redis://localhost:6379
export S3_ENDPOINT=http://localhost:9000
```

### Query Service (Python FastAPI)

```bash
# Location
cd services/query-service

# Install dependencies
poetry install

# Run with auto-reload
poetry run uvicorn aswa_query.main:app --reload --port 8002

# Run tests
poetry run pytest tests/ -v
```

**Environment Variables:**
```bash
export DATABASE_URL=postgresql+asyncpg://aswa:aswa@localhost:5432/aswa
export REDIS_URL=redis://localhost:6379
export OPENAI_API_KEY=sk-...  # or ANTHROPIC_API_KEY
```

### Insight Engine (Python FastAPI)

```bash
# Location
cd services/insight-service

# Install dependencies
poetry install

# Run with auto-reload
poetry run uvicorn aswa_insight.main:app --reload --port 8003

# Run tests
poetry run pytest tests/ -v
```

### Web Dashboard (React/Vite)

```bash
# Location
cd services/web-dashboard

# Install dependencies
npm install

# Run dev server (hot reload)
npm run dev

# Run tests
npm test

# Build for production
npm run build

# Preview production build
npm run preview
```

**Environment Variables:**
```bash
export VITE_API_URL=http://localhost:8000
```

### Agent Service (Python FastAPI)

```bash
# Location
cd services/agent-service

# Install dependencies
poetry install

# Run with auto-reload
poetry run uvicorn aswa_agents.main:app --reload --port 8090

# Run tests
poetry run pytest tests/ -v
```

---

## Common Tasks

### Database Operations

```bash
# Connect to PostgreSQL
./scripts/dev.sh db shell

# Run migrations
./scripts/dev.sh db migrate

# Seed test data
./scripts/dev.sh db seed

# Reset database (WARNING: deletes all data)
./scripts/dev.sh db reset
```

### View Logs

```bash
# All services
./scripts/dev.sh logs

# Specific service
./scripts/dev.sh logs api-gateway
./scripts/dev.sh logs ingestion-service
./scripts/dev.sh logs query-service
```

### Open Shell in Container

```bash
# API Gateway
./scripts/dev.sh shell api-gateway

# PostgreSQL
./scripts/dev.sh shell postgres

# Redis CLI
./scripts/dev.sh shell redis
```

### Run Tests

```bash
# All tests
./scripts/dev.sh test all

# Specific service
./scripts/dev.sh test ingestion
./scripts/dev.sh test query
./scripts/dev.sh test api-gateway
./scripts/dev.sh test web
```

### Clean Up

```bash
# Stop services
./scripts/dev.sh down

# Stop and remove all data
./scripts/dev.sh clean
```

---

## Development Workflow

### Typical Day

```bash
# Morning: Start services
./scripts/dev.sh up

# Check everything is running
./scripts/dev.sh status

# Work on code...
# (Services auto-reload on file changes)

# View logs if needed
./scripts/dev.sh logs ingestion-service

# Run tests before committing
./scripts/dev.sh test ingestion

# Evening: Stop services
./scripts/dev.sh down
```

### Working on a Single Service

```bash
# Start only dependencies
docker-compose up -d postgres redis elasticsearch minio

# Run your service natively with hot reload
cd services/ingestion-service
poetry run uvicorn aswa_ingestion.main:app --reload --port 8001
```

### Debugging Python Services

```bash
# Run with debugpy
poetry run python -m debugpy --listen 5678 --wait-for-client \
  -m uvicorn aswa_ingestion.main:app --port 8001

# In VS Code, attach debugger to port 5678
```

**VS Code launch.json:**
```json
{
  "name": "Attach to Python",
  "type": "python",
  "request": "attach",
  "connect": {
    "host": "localhost",
    "port": 5678
  }
}
```

### Debugging Java Services

```bash
# Run with debug port
./gradlew bootRun --debug-jvm

# Debugger listens on port 5005
```

**VS Code/IntelliJ:**
- Attach remote debugger to `localhost:5005`

---

## Port Reference

| Port | Service |
|------|---------|
| 3000 | Web Dashboard |
| 5432 | PostgreSQL |
| 6379 | Redis |
| 8000 | API Gateway |
| 8001 | Ingestion Service |
| 8002 | Query Service |
| 8003 | Insight Engine |
| 8090 | Agent Service |
| 9000 | MinIO API |
| 9001 | MinIO Console |
| 9200 | Elasticsearch |
| 16686 | Jaeger UI |
| 8025 | Mailpit UI |

---

## Troubleshooting

### Docker Issues

**"Cannot connect to Docker daemon"**
```bash
# Make sure Docker Desktop is running
open -a Docker

# Wait for it to start, then retry
./scripts/dev.sh up
```

**"Port already in use"**
```bash
# Find what's using the port
lsof -i :8000

# Kill it
kill -9 <PID>

# Or change the port in docker-compose.yaml
```

**"Out of memory"**
```bash
# Check Docker memory usage
docker stats

# Increase Docker Desktop memory limit
# Docker Desktop → Settings → Resources → Memory

# Or run in lightweight mode
./scripts/dev.sh down
docker-compose up -d postgres redis
# Run services natively
```

### Database Issues

**"Connection refused"**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

**"Database does not exist"**
```bash
# Run migrations
./scripts/dev.sh db migrate
```

### Service Issues

**"Service won't start"**
```bash
# Check logs
./scripts/dev.sh logs <service-name>

# Check if dependencies are running
./scripts/dev.sh status

# Rebuild the service
./scripts/dev.sh build <service-name>
./scripts/dev.sh up
```

**"Import errors in Python services"**
```bash
# Reinstall dependencies
cd services/<service-name>
poetry install

# Or rebuild Docker image
./scripts/dev.sh build <service-name>
```

### Performance Issues

**"Everything is slow"**
```bash
# Check resource usage
docker stats

# Solutions:
# 1. Increase Docker Desktop resources
# 2. Run in lightweight mode
# 3. Stop unused services
docker-compose stop elasticsearch jaeger
```

**"Hot reload not working"**
```bash
# For Python: Check uvicorn is running with --reload
# For React: Check Vite is running (not build)
# For Java: Use bootRun, not java -jar

# Volume mounts might be slow on Mac
# Add to docker-compose.yaml for better performance:
volumes:
  - type: bind
    source: ./src
    target: /app/src
    consistency: cached
```

---

## Tips for M1/M2/M3 Macs

Apple Silicon Macs work great! A few notes:

1. **Rosetta not needed** - All images support arm64
2. **Better performance** - Docker runs faster on Apple Silicon
3. **Less memory** - Can often use 6GB instead of 8GB
4. **Watch for x86 images** - Some older images may need:
   ```yaml
   platform: linux/amd64
   ```

---

## IDE Setup

### VS Code Extensions

```bash
# Recommended extensions
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension vscjava.vscode-java-pack
code --install-extension ms-azuretools.vscode-docker
```

### PyCharm/IntelliJ

1. Open project root
2. Mark directories as Sources Root:
   - `services/*/src`
   - `libs/*/src`
3. Configure Python interpreter per service
4. Configure Database tools for PostgreSQL

---

## Getting Help

- **Logs**: `./scripts/dev.sh logs`
- **Status**: `./scripts/dev.sh status`
- **Shell**: `./scripts/dev.sh shell <service>`
- **Info**: `./scripts/dev.sh info`
- **Help**: `./scripts/dev.sh help`

---

*Happy coding!* 🚀
