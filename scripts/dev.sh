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

    print_success "Prerequisites checked"
}

# Start services
start_services() {
    local profile="${1:-}"

    print_info "Starting ASWA services..."

    if [ -z "$profile" ]; then
        print_info "Starting core services (postgres, redis)..."
        docker-compose up -d
    elif [ "$profile" == "all" ]; then
        print_info "Starting all services..."
        docker-compose --profile services --profile tools up -d
    elif [ "$profile" == "services" ]; then
        print_info "Starting services with API Gateway..."
        docker-compose --profile services up -d
    elif [ "$profile" == "tools" ]; then
        print_info "Starting with management tools..."
        docker-compose --profile tools up -d
    else
        print_error "Unknown profile: $profile"
        print_info "Available profiles: services, tools, all"
        exit 1
    fi

    print_success "Services started"
    show_status
}

# Stop services
stop_services() {
    print_info "Stopping ASWA services..."
    docker-compose down
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
    docker-compose ps
}

# Show logs
show_logs() {
    local service="${1:-}"

    if [ -z "$service" ]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$service"
    fi
}

# Clean up all data
clean_data() {
    print_warning "This will delete all Docker volumes and data!"
    read -p "Are you sure? (yes/no): " -n 3 -r
    echo

    if [[ $REPLY == "yes" ]]; then
        print_info "Cleaning up all data..."
        docker-compose down -v
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
        docker-compose build
    else
        print_info "Building $service..."
        docker-compose build "$service"
    fi

    print_success "Build completed"
}

# Run database migrations
run_migrations() {
    print_info "Running database migrations..."

    if [ -f "./scripts/db-migrate.sh" ]; then
        ./scripts/db-migrate.sh migrate dev
    else
        print_error "Migration script not found"
        exit 1
    fi

    print_success "Migrations completed"
}

# Show connection info
show_info() {
    echo ""
    print_info "=== ASWA Development Environment ==="
    echo ""
    echo "PostgreSQL:"
    echo "  Host: localhost:5432"
    echo "  Database: aswa"
    echo "  User: aswa"
    echo "  Password: aswa_dev_password"
    echo "  Connection: psql -h localhost -U aswa -d aswa"
    echo ""
    echo "Redis:"
    echo "  Host: localhost:6379"
    echo "  Password: aswa_dev_password"
    echo "  Connection: redis-cli -h localhost -p 6379 -a aswa_dev_password"
    echo ""
    echo "API Gateway:"
    echo "  URL: http://localhost:8080"
    echo "  Health: http://localhost:8080/health"
    echo "  Swagger: http://localhost:8080/swagger-ui.html"
    echo ""
    echo "PgAdmin:"
    echo "  URL: http://localhost:5050"
    echo "  Email: admin@aswa.local"
    echo "  Password: admin"
    echo ""
    echo "Redis Commander:"
    echo "  URL: http://localhost:8081"
    echo ""
}

# Show help
show_help() {
    cat << EOF
ASWA Development Environment Manager

Usage: ./dev.sh [command] [options]

Commands:
    start [profile]     Start services (profiles: services, tools, all)
    stop               Stop all services
    restart [profile]  Restart services
    status             Show service status
    logs [service]     Show logs (optionally for specific service)
    build [service]    Build Docker images
    migrate            Run database migrations
    clean              Clean all data (WARNING: deletes volumes)
    info               Show connection information
    help               Show this help message

Examples:
    ./dev.sh start                    # Start core services
    ./dev.sh start services           # Start with API Gateway
    ./dev.sh start all                # Start everything
    ./dev.sh logs api-gateway         # Show API Gateway logs
    ./dev.sh build api-gateway        # Rebuild API Gateway
    ./dev.sh migrate                  # Run migrations
    ./dev.sh clean                    # Clean all data

EOF
}

# Main script
main() {
    check_prerequisites

    case "${1:-help}" in
        start)
            start_services "${2:-}"
            ;;
        stop)
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
        build)
            build_services "${2:-}"
            ;;
        migrate)
            run_migrations
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
