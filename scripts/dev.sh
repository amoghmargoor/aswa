#!/usr/bin/env bash
#
# ASWA Development Environment Manager
# Manages Docker Compose services for local development
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if docker and docker-compose are installed
check_prerequisites() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
}

# Start services
start_services() {
    local profile="${1:-}"

    print_info "Starting ASWA services..."

    if [ -z "$profile" ]; then
        print_info "Starting all development services..."
        docker-compose -f infrastructure/docker/docker-compose.yaml up -d
    elif [ "$profile" == "--build" ]; then
        print_info "Building and starting services..."
        docker-compose -f infrastructure/docker/docker-compose.yaml up -d --build
    elif [ "$profile" == "all" ]; then
        print_info "Starting all services..."
        docker-compose -f infrastructure/docker/docker-compose.yaml --profile services --profile tools up -d
    elif [ "$profile" == "services" ]; then
        print_info "Starting services with API Gateway..."
        docker-compose -f infrastructure/docker/docker-compose.yaml --profile services up -d
    elif [ "$profile" == "tools" ]; then
        print_info "Starting with management tools..."
        docker-compose -f infrastructure/docker/docker-compose.yaml --profile tools up -d
    else
        print_error "Unknown profile: $profile"
        print_info "Available profiles: services, tools, all, or --build"
        exit 1
    fi

    print_success "Services started. Waiting for health checks..."
    sleep 5

    show_status
    echo ""
    print_info "Access points:"
    echo "  Web Dashboard:  http://localhost:3000"
    echo "  API Gateway:    http://localhost:8000"
    echo "  API Docs:       http://localhost:8000/docs"
    echo "  Jaeger:         http://localhost:16686"
    echo "  Mailpit:        http://localhost:8025"
    echo "  MinIO Console:  http://localhost:9001"
}

# Stop services
stop_services() {
    print_info "Stopping ASWA services..."
    docker-compose -f infrastructure/docker/docker-compose.yaml down
    print_success "Services stopped"
}

# Restart services
restart_services() {
    stop_services
    start_services "$@"
}

# Show service status
show_status() {
    print_info "Service Status:"
    docker-compose -f infrastructure/docker/docker-compose.yaml ps
}

# Show logs
show_logs() {
    local service="${1:-}"

    if [ -z "$service" ]; then
        docker-compose -f infrastructure/docker/docker-compose.yaml logs -f
    else
        docker-compose -f infrastructure/docker/docker-compose.yaml logs -f "$service"
    fi
}

# Open shell in container
open_shell() {
    if [ -z "$1" ]; then
        print_error "Please specify a service name"
        echo "Available services: api-gateway, ingestion-service, query-service, insight-service, web-dashboard, postgres, redis"
        exit 1
    fi

    case "$1" in
        api-gateway)
            docker-compose -f infrastructure/docker/docker-compose.yaml exec api-gateway /bin/bash
            ;;
        web-dashboard)
            docker-compose -f infrastructure/docker/docker-compose.yaml exec web-dashboard /bin/sh
            ;;
        postgres)
            docker-compose -f infrastructure/docker/docker-compose.yaml exec postgres psql -U aswa
            ;;
        redis)
            docker-compose -f infrastructure/docker/docker-compose.yaml exec redis redis-cli
            ;;
        *)
            docker-compose -f infrastructure/docker/docker-compose.yaml exec "$1" /bin/bash
            ;;
    esac
}

# Database commands
db_command() {
    case "$1" in
        migrate)
            print_info "Running database migrations..."
            docker-compose -f infrastructure/docker/docker-compose.yaml exec ingestion-service alembic upgrade head
            print_success "Migrations complete"
            ;;
        seed)
            print_info "Seeding database..."
            docker-compose -f infrastructure/docker/docker-compose.yaml exec ingestion-service python -m aswa_ingestion.scripts.seed
            print_success "Database seeded"
            ;;
        reset)
            print_warning "Resetting database..."
            docker-compose -f infrastructure/docker/docker-compose.yaml exec postgres psql -U aswa -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
            db_command migrate
            db_command seed
            print_success "Database reset complete"
            ;;
        shell)
            docker-compose -f infrastructure/docker/docker-compose.yaml exec postgres psql -U aswa
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
run_tests() {
    # Start test containers
    print_info "Starting test containers..."
    docker-compose -f infrastructure/docker/docker-compose.test.yaml up -d

    # Wait for services
    sleep 10

    case "$1" in
        ingestion|ingestion-service)
            print_info "Running ingestion service tests..."
            cd "$PROJECT_ROOT/services/ingestion-service"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ELASTICSEARCH_URL="http://localhost:9201" \
            pytest tests/ -v --cov=src --cov-report=html
            ;;
        query|query-service)
            print_info "Running query service tests..."
            cd "$PROJECT_ROOT/services/query-service"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ELASTICSEARCH_URL="http://localhost:9201" \
            pytest tests/ -v --cov=src --cov-report=html
            ;;
        insight|insight-service)
            print_info "Running insight service tests..."
            cd "$PROJECT_ROOT/services/insight-service"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ELASTICSEARCH_URL="http://localhost:9201" \
            pytest tests/ -v --cov=src --cov-report=html
            ;;
        api-gateway)
            print_info "Running API gateway tests..."
            cd "$PROJECT_ROOT/services/api-gateway"
            DATABASE_URL="postgresql://aswa:aswa@localhost:5433/aswa_test" \
            REDIS_URL="redis://localhost:6380" \
            ./gradlew test
            ;;
        web|web-dashboard)
            print_info "Running web dashboard tests..."
            cd "$PROJECT_ROOT/services/web-dashboard"
            npm test
            ;;
        all|"")
            run_tests ingestion
            run_tests query
            run_tests insight
            run_tests api-gateway
            run_tests web
            ;;
        *)
            echo "Unknown service: $1"
            echo "Available: ingestion, query, insight, api-gateway, web, all"
            exit 1
            ;;
    esac

    # Cleanup
    docker-compose -f infrastructure/docker/docker-compose.test.yaml down -v
}

# Clean up all data
clean_data() {
    print_warning "This will delete all Docker volumes and data!"
    read -p "Are you sure? (yes/no): " -r
    echo

    if [[ $REPLY == "yes" ]]; then
        print_info "Cleaning up all data..."
        docker-compose -f infrastructure/docker/docker-compose.yaml down -v --remove-orphans

        # Remove dangling images
        docker image prune -f

        # Clean build caches
        print_info "Cleaning build caches..."

        # Python
        find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$PROJECT_ROOT" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
        find "$PROJECT_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

        # Node
        rm -rf "$PROJECT_ROOT/services/web-dashboard/node_modules" 2>/dev/null || true

        # Java
        rm -rf "$PROJECT_ROOT/services/api-gateway/build" 2>/dev/null || true
        rm -rf "$PROJECT_ROOT/libs/common-java/build" 2>/dev/null || true

        print_success "All data cleaned"
    else
        print_info "Cleanup cancelled"
    fi
}

# Build services
build_services() {
    local service="${1:-}"

    if [ -z "$service" ]; then
        print_info "Building all services..."
        docker-compose -f infrastructure/docker/docker-compose.yaml build
    else
        print_info "Building $service..."
        docker-compose -f infrastructure/docker/docker-compose.yaml build "$service"
    fi

    print_success "Build completed"
}

# Initial setup
initial_setup() {
    print_info "Setting up ASWA development environment..."

    # Check prerequisites
    echo "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is required"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        print_warning "Python 3 not found"
    fi

    if ! command -v node &> /dev/null; then
        print_warning "Node.js not found"
    fi

    if ! command -v java &> /dev/null; then
        print_warning "Java not found"
    fi

    # Copy environment files
    if [ ! -f "$PROJECT_ROOT/infrastructure/docker/.env" ]; then
        cp "$PROJECT_ROOT/infrastructure/docker/.env.example" \
           "$PROJECT_ROOT/infrastructure/docker/.env"
        print_success "Created .env file"
        print_warning "Please update .env with your API keys"
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
    print_success "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Update infrastructure/docker/.env with your API keys"
    echo "  2. Run './scripts/dev.sh up' to start services"
    echo "  3. Access the dashboard at http://localhost:3000"
}

# Show connection info
show_info() {
    echo ""
    print_info "=== ASWA Development Environment ==="
    echo ""
    echo "Core Services:"
    echo "  Web Dashboard:   http://localhost:3000"
    echo "  API Gateway:     http://localhost:8000"
    echo "  API Docs:        http://localhost:8000/docs"
    echo ""
    echo "Databases:"
    echo "  PostgreSQL:      localhost:5432 (user: aswa, password: aswa)"
    echo "  Redis:           localhost:6379"
    echo "  Elasticsearch:   http://localhost:9200"
    echo ""
    echo "Storage:"
    echo "  MinIO Console:   http://localhost:9001 (admin: minioadmin/minioadmin)"
    echo ""
    echo "Observability:"
    echo "  Jaeger:          http://localhost:16686"
    echo ""
    echo "Testing:"
    echo "  Mailpit:         http://localhost:8025"
    echo ""
}

# Show help
show_help() {
    cat << EOF
ASWA Development Environment Manager

Usage: ./dev.sh [command] [options]

Commands:
    up [--build|profile]  Start services (profiles: services, tools, all, --build)
    down                  Stop all services
    restart [profile]     Restart services
    status                Show service status
    logs [service]        Show logs (optionally for specific service)
    shell <service>       Open shell in service container
    db <command>          Database commands (migrate, seed, reset, shell)
    test [service]        Run tests (ingestion, query, insight, api-gateway, web, all)
    build [service]       Build Docker images
    setup                 Initial project setup
    clean                 Clean all data (WARNING: deletes volumes)
    info                  Show connection information
    help                  Show this help message

Examples:
    ./dev.sh up                    # Start all services
    ./dev.sh up --build            # Build and start services
    ./dev.sh logs api-gateway      # Show API Gateway logs
    ./dev.sh shell ingestion-service   # Open shell in ingestion service
    ./dev.sh db migrate            # Run database migrations
    ./dev.sh test ingestion        # Run ingestion service tests
    ./dev.sh test all              # Run all tests

EOF
}

# Main script
main() {
    check_prerequisites

    case "${1:-help}" in
        up)
            start_services "${2:-}"
            ;;
        down)
            stop_services
            ;;
        restart)
            restart_services "${2:-}"
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "${2:-}"
            ;;
        shell)
            open_shell "${2:-}"
            ;;
        db)
            db_command "${2:-}"
            ;;
        test)
            run_tests "${2:-}"
            ;;
        build)
            build_services "${2:-}"
            ;;
        setup)
            initial_setup
            ;;
        clean)
            clean_data
            ;;
        info)
            show_info
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
