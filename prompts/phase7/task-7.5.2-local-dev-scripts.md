# Task 7.5.2: Local Development - Development Scripts

## Context

You are setting up local development environment for ASWA. Docker Compose is complete. Now we need helper scripts for common development tasks.

## Objective

Create development scripts that:
1. Simplify common operations
2. Run database migrations
3. Seed test data
4. Generate API clients
5. Support developer workflow

## Requirements

### 1. Create `/scripts/dev.sh`
```bash
#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Help function
show_help() {
    echo -e "${BLUE}ASWA Development Helper${NC}"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  up              Start all services"
    echo "  down            Stop all services"
    echo "  restart         Restart all services"
    echo "  logs [service]  View logs (optionally for specific service)"
    echo "  shell <service> Open shell in service container"
    echo "  db              Database commands (migrate, seed, reset)"
    echo "  test            Run tests"
    echo "  build           Build all services"
    echo "  clean           Clean up volumes and caches"
    echo "  status          Show service status"
    echo "  setup           Initial project setup"
    echo ""
    echo "Examples:"
    echo "  $0 up                    # Start all services"
    echo "  $0 logs api-gateway      # View API gateway logs"
    echo "  $0 db migrate            # Run database migrations"
    echo "  $0 test ingestion        # Run ingestion service tests"
}

# Check Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running${NC}"
        exit 1
    fi
}

# Start services
cmd_up() {
    check_docker
    echo -e "${GREEN}Starting ASWA services...${NC}"
    cd "$PROJECT_ROOT/infrastructure/docker"

    if [ "$1" == "--build" ]; then
        docker-compose up -d --build
    else
        docker-compose up -d
    fi

    echo -e "${GREEN}Services started. Waiting for health checks...${NC}"
    sleep 5

    cmd_status
    echo ""
    echo -e "${BLUE}Access points:${NC}"
    echo "  Web Dashboard:  http://localhost:3000"
    echo "  API Gateway:    http://localhost:8000"
    echo "  API Docs:       http://localhost:8000/docs"
    echo "  Jaeger:         http://localhost:16686"
    echo "  Mailpit:        http://localhost:8025"
    echo "  MinIO Console:  http://localhost:9001"
}

# Stop services
cmd_down() {
    check_docker
    echo -e "${YELLOW}Stopping ASWA services...${NC}"
    cd "$PROJECT_ROOT/infrastructure/docker"
    docker-compose down
    echo -e "${GREEN}Services stopped${NC}"
}

# Restart services
cmd_restart() {
    cmd_down
    cmd_up "$@"
}

# View logs
cmd_logs() {
    check_docker
    cd "$PROJECT_ROOT/infrastructure/docker"

    if [ -n "$1" ]; then
        docker-compose logs -f "$1"
    else
        docker-compose logs -f
    fi
}

# Open shell in container
cmd_shell() {
    check_docker
    if [ -z "$1" ]; then
        echo -e "${RED}Error: Please specify a service name${NC}"
        echo "Available services: api-gateway, ingestion-service, query-service, insight-service, web-dashboard"
        exit 1
    fi

    cd "$PROJECT_ROOT/infrastructure/docker"

    case "$1" in
        api-gateway)
            docker-compose exec api-gateway /bin/bash
            ;;
        web-dashboard)
            docker-compose exec web-dashboard /bin/sh
            ;;
        *)
            docker-compose exec "$1" /bin/bash
            ;;
    esac
}

# Database commands
cmd_db() {
    check_docker
    case "$1" in
        migrate)
            echo -e "${BLUE}Running database migrations...${NC}"
            docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.yaml" \
                exec ingestion-service alembic upgrade head
            echo -e "${GREEN}Migrations complete${NC}"
            ;;
        seed)
            echo -e "${BLUE}Seeding database...${NC}"
            docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.yaml" \
                exec ingestion-service python -m aswa_ingestion.scripts.seed
            echo -e "${GREEN}Database seeded${NC}"
            ;;
        reset)
            echo -e "${YELLOW}Resetting database...${NC}"
            docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.yaml" \
                exec postgres psql -U aswa -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
            cmd_db migrate
            cmd_db seed
            echo -e "${GREEN}Database reset complete${NC}"
            ;;
        shell)
            docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.yaml" \
                exec postgres psql -U aswa
            ;;
        *)
            echo "Database commands:"
            echo "  migrate  - Run database migrations"
            echo "  seed     - Seed test data"
            echo "  reset    - Reset database (destructive!)"
            echo "  shell    - Open PostgreSQL shell"
            ;;
    esac
}

# Run tests
cmd_test() {
    check_docker

    # Start test containers
    echo -e "${BLUE}Starting test containers...${NC}"
    docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.test.yaml" up -d

    # Wait for services
    sleep 10

    case "$1" in
        ingestion|ingestion-service)
            echo -e "${BLUE}Running ingestion service tests...${NC}"
            cd "$PROJECT_ROOT/services/ingestion-service"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ELASTICSEARCH_URL="http://localhost:9201" \
            pytest tests/ -v --cov=src --cov-report=html
            ;;
        query|query-service)
            echo -e "${BLUE}Running query service tests...${NC}"
            cd "$PROJECT_ROOT/services/query-service"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ELASTICSEARCH_URL="http://localhost:9201" \
            pytest tests/ -v --cov=src --cov-report=html
            ;;
        insight|insight-service)
            echo -e "${BLUE}Running insight service tests...${NC}"
            cd "$PROJECT_ROOT/services/insight-service"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ELASTICSEARCH_URL="http://localhost:9201" \
            pytest tests/ -v --cov=src --cov-report=html
            ;;
        api-gateway)
            echo -e "${BLUE}Running API gateway tests...${NC}"
            cd "$PROJECT_ROOT/services/api-gateway"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ./gradlew test
            ;;
        web|web-dashboard)
            echo -e "${BLUE}Running web dashboard tests...${NC}"
            cd "$PROJECT_ROOT/services/web-dashboard"
            npm test
            ;;
        all|"")
            cmd_test ingestion
            cmd_test query
            cmd_test insight
            cmd_test api-gateway
            cmd_test web
            ;;
        *)
            echo "Unknown service: $1"
            echo "Available: ingestion, query, insight, api-gateway, web, all"
            exit 1
            ;;
    esac

    # Cleanup
    docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.test.yaml" down -v
}

# Build services
cmd_build() {
    check_docker
    echo -e "${BLUE}Building ASWA services...${NC}"

    if [ -n "$1" ]; then
        docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.yaml" \
            build "$1"
    else
        docker-compose -f "$PROJECT_ROOT/infrastructure/docker/docker-compose.yaml" \
            build
    fi

    echo -e "${GREEN}Build complete${NC}"
}

# Clean up
cmd_clean() {
    check_docker
    echo -e "${YELLOW}Cleaning up...${NC}"

    cd "$PROJECT_ROOT/infrastructure/docker"
    docker-compose down -v --remove-orphans

    # Remove dangling images
    docker image prune -f

    # Clean build caches
    echo -e "${BLUE}Cleaning build caches...${NC}"

    # Python
    find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

    # Node
    rm -rf "$PROJECT_ROOT/services/web-dashboard/node_modules" 2>/dev/null || true

    # Java
    rm -rf "$PROJECT_ROOT/services/api-gateway/build" 2>/dev/null || true
    rm -rf "$PROJECT_ROOT/libs/common-java/build" 2>/dev/null || true

    echo -e "${GREEN}Cleanup complete${NC}"
}

# Show status
cmd_status() {
    check_docker
    cd "$PROJECT_ROOT/infrastructure/docker"
    echo -e "${BLUE}Service Status:${NC}"
    docker-compose ps
}

# Initial setup
cmd_setup() {
    echo -e "${BLUE}Setting up ASWA development environment...${NC}"

    # Check prerequisites
    echo "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is required${NC}"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Warning: Python 3 not found${NC}"
    fi

    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Warning: Node.js not found${NC}"
    fi

    if ! command -v java &> /dev/null; then
        echo -e "${YELLOW}Warning: Java not found${NC}"
    fi

    # Copy environment files
    if [ ! -f "$PROJECT_ROOT/infrastructure/docker/.env" ]; then
        cp "$PROJECT_ROOT/infrastructure/docker/.env.example" \
           "$PROJECT_ROOT/infrastructure/docker/.env"
        echo -e "${GREEN}Created .env file${NC}"
        echo -e "${YELLOW}Please update .env with your API keys${NC}"
    fi

    # Install Python dependencies
    echo "Installing Python dependencies..."
    pip install -e "$PROJECT_ROOT/libs/common-python[dev]" 2>/dev/null || true

    for service in ingestion-service query-service insight-service; do
        if [ -f "$PROJECT_ROOT/services/$service/pyproject.toml" ]; then
            pip install -e "$PROJECT_ROOT/services/$service[dev]" 2>/dev/null || true
        fi
    done

    # Install Node dependencies
    if [ -f "$PROJECT_ROOT/services/web-dashboard/package.json" ]; then
        echo "Installing Node.js dependencies..."
        cd "$PROJECT_ROOT/services/web-dashboard"
        npm install
    fi

    # Build Java projects
    if [ -f "$PROJECT_ROOT/libs/common-java/build.gradle" ]; then
        echo "Building Java projects..."
        cd "$PROJECT_ROOT/libs/common-java"
        ./gradlew build publishToMavenLocal 2>/dev/null || true
    fi

    echo ""
    echo -e "${GREEN}Setup complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Update infrastructure/docker/.env with your API keys"
    echo "  2. Run './scripts/dev.sh up' to start services"
    echo "  3. Access the dashboard at http://localhost:3000"
}

# Main
case "$1" in
    up)
        shift
        cmd_up "$@"
        ;;
    down)
        cmd_down
        ;;
    restart)
        shift
        cmd_restart "$@"
        ;;
    logs)
        shift
        cmd_logs "$@"
        ;;
    shell)
        shift
        cmd_shell "$@"
        ;;
    db)
        shift
        cmd_db "$@"
        ;;
    test)
        shift
        cmd_test "$@"
        ;;
    build)
        shift
        cmd_build "$@"
        ;;
    clean)
        cmd_clean
        ;;
    status)
        cmd_status
        ;;
    setup)
        cmd_setup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
```

### 2. Create `/scripts/generate-api-client.sh`
```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Generating API clients from OpenAPI spec..."

# Ensure the API is running
if ! curl -s http://localhost:8000/openapi.json > /dev/null; then
    echo "Error: API Gateway is not running. Start it with './scripts/dev.sh up'"
    exit 1
fi

# Download OpenAPI spec
curl -s http://localhost:8000/openapi.json > /tmp/openapi.json

# Generate TypeScript client
echo "Generating TypeScript client..."
npx @openapitools/openapi-generator-cli generate \
    -i /tmp/openapi.json \
    -g typescript-fetch \
    -o "$PROJECT_ROOT/services/web-dashboard/src/api/generated" \
    --additional-properties=supportsES6=true,typescriptThreePlus=true

echo "API client generated at services/web-dashboard/src/api/generated/"
```

### 3. Create `/scripts/seed-data.py`
```python
#!/usr/bin/env python3
"""Seed development database with test data."""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import random
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://aswa:aswa@localhost:5432/aswa"
)


async def seed_database():
    """Seed the database with test data."""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get dev tenant
        result = await session.execute(
            "SELECT id FROM users.tenants WHERE slug = 'dev'"
        )
        tenant_row = result.fetchone()
        if not tenant_row:
            print("Dev tenant not found. Run migrations first.")
            return

        tenant_id = tenant_row[0]
        print(f"Seeding data for tenant: {tenant_id}")

        # Create test users
        users = [
            ("alice@aswa.local", "Alice Smith", "analyst"),
            ("bob@aswa.local", "Bob Johnson", "user"),
            ("carol@aswa.local", "Carol Williams", "admin"),
        ]

        for email, name, role in users:
            await session.execute(
                """
                INSERT INTO users.users (tenant_id, email, name, password_hash, role)
                VALUES (:tenant_id, :email, :name, :password_hash, :role)
                ON CONFLICT (tenant_id, email) DO NOTHING
                """,
                {
                    "tenant_id": tenant_id,
                    "email": email,
                    "name": name,
                    "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.Vzn7Xo5NeZ0Kq6",
                    "role": role,
                }
            )

        # Create sample documents
        document_types = ["pdf", "docx", "xlsx", "txt"]
        document_names = [
            "Q4 Financial Report",
            "Marketing Strategy 2024",
            "Technical Architecture",
            "Risk Assessment Document",
            "Compliance Audit Report",
            "Product Roadmap",
            "Customer Survey Results",
            "Operations Manual",
        ]

        document_ids = []
        for name in document_names:
            doc_id = str(uuid.uuid4())
            doc_type = random.choice(document_types)
            await session.execute(
                """
                INSERT INTO documents.documents
                (id, tenant_id, name, content_type, size_bytes, status, created_at, processed_at)
                VALUES (:id, :tenant_id, :name, :content_type, :size_bytes, :status, :created_at, :processed_at)
                ON CONFLICT DO NOTHING
                """,
                {
                    "id": doc_id,
                    "tenant_id": tenant_id,
                    "name": f"{name}.{doc_type}",
                    "content_type": f"application/{doc_type}",
                    "size_bytes": random.randint(10000, 5000000),
                    "status": "processed",
                    "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                    "processed_at": datetime.utcnow() - timedelta(days=random.randint(0, 29)),
                }
            )
            document_ids.append(doc_id)

        # Create sample insights
        insight_types = ["risk", "opportunity"]
        severities = ["low", "medium", "high", "critical"]
        categories = ["financial", "operational", "compliance", "strategic"]

        insight_titles = [
            "Budget overrun risk identified",
            "Cost reduction opportunity",
            "Compliance gap detected",
            "Market expansion opportunity",
            "Resource constraint warning",
            "Process optimization potential",
            "Security vulnerability flagged",
            "Revenue growth opportunity",
        ]

        for i, title in enumerate(insight_titles):
            await session.execute(
                """
                INSERT INTO insights.insights
                (tenant_id, document_id, type, category, title, description, severity, confidence, created_at)
                VALUES (:tenant_id, :document_id, :type, :category, :title, :description, :severity, :confidence, :created_at)
                """,
                {
                    "tenant_id": tenant_id,
                    "document_id": random.choice(document_ids),
                    "type": random.choice(insight_types),
                    "category": random.choice(categories),
                    "title": title,
                    "description": f"Detailed analysis of {title.lower()}. This insight was automatically generated based on document analysis.",
                    "severity": random.choice(severities),
                    "confidence": random.uniform(0.7, 0.99),
                    "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 14)),
                }
            )

        await session.commit()
        print("Database seeded successfully!")
        print(f"  - Created {len(users)} users")
        print(f"  - Created {len(document_names)} documents")
        print(f"  - Created {len(insight_titles)} insights")


if __name__ == "__main__":
    asyncio.run(seed_database())
```

### 4. Create `/Makefile`
```makefile
.PHONY: help up down logs test build clean setup

# Default target
help:
	@echo "ASWA Development Commands"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  up        Start all services"
	@echo "  down      Stop all services"
	@echo "  logs      View logs"
	@echo "  test      Run all tests"
	@echo "  build     Build all services"
	@echo "  clean     Clean up"
	@echo "  setup     Initial setup"
	@echo "  lint      Run linters"
	@echo "  format    Format code"

# Start services
up:
	@./scripts/dev.sh up

# Stop services
down:
	@./scripts/dev.sh down

# View logs
logs:
	@./scripts/dev.sh logs

# Run tests
test:
	@./scripts/dev.sh test all

test-python:
	@./scripts/dev.sh test ingestion
	@./scripts/dev.sh test query
	@./scripts/dev.sh test insight

test-java:
	@./scripts/dev.sh test api-gateway

test-web:
	@./scripts/dev.sh test web

# Build
build:
	@./scripts/dev.sh build

# Clean
clean:
	@./scripts/dev.sh clean

# Setup
setup:
	@./scripts/dev.sh setup

# Database
db-migrate:
	@./scripts/dev.sh db migrate

db-seed:
	@./scripts/dev.sh db seed

db-reset:
	@./scripts/dev.sh db reset

# Lint
lint: lint-python lint-java lint-web

lint-python:
	@echo "Linting Python..."
	@ruff check services/ libs/common-python/
	@mypy services/ingestion-service/src services/query-service/src services/insight-service/src --ignore-missing-imports

lint-java:
	@echo "Linting Java..."
	@cd services/api-gateway && ./gradlew spotlessCheck

lint-web:
	@echo "Linting TypeScript..."
	@cd services/web-dashboard && npm run lint

# Format
format: format-python format-java format-web

format-python:
	@echo "Formatting Python..."
	@ruff format services/ libs/common-python/
	@ruff check --fix services/ libs/common-python/

format-java:
	@echo "Formatting Java..."
	@cd services/api-gateway && ./gradlew spotlessApply

format-web:
	@echo "Formatting TypeScript..."
	@cd services/web-dashboard && npm run format

# Generate API client
api-client:
	@./scripts/generate-api-client.sh
```

## Verification

1. Make scripts executable: `chmod +x scripts/*.sh`
2. Run setup: `./scripts/dev.sh setup`
3. Start services: `make up`
4. Run tests: `make test`
5. View logs: `make logs`
