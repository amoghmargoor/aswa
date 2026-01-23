#!/bin/bash
# ASWA Database Migration Script
# Uses Flyway for database versioning and migrations
#
# Usage: ./db-migrate.sh [command] [environment]
#
# Commands:
#   migrate   - Run pending migrations
#   info      - Show migration status
#   validate  - Validate migrations
#   clean     - Drop all objects (USE WITH CAUTION)
#   baseline  - Baseline existing database
#   repair    - Repair schema history table
#
# Environments:
#   dev       - Local development (default)
#   test      - Test environment
#   prod      - Production environment

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$PROJECT_ROOT/migrations/postgresql"

# Default values
COMMAND="${1:-migrate}"
ENVIRONMENT="${2:-dev}"

# Flyway version
FLYWAY_VERSION="10.7.1"
FLYWAY_URL="https://repo1.maven.org/maven2/org/flywaydb/flyway-commandline/${FLYWAY_VERSION}/flyway-commandline-${FLYWAY_VERSION}.tar.gz"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if flyway is installed
check_flyway() {
    if ! command -v flyway &> /dev/null; then
        print_warning "Flyway not found. Attempting to download..."
        install_flyway
    fi
}

# Function to install flyway
install_flyway() {
    local install_dir="$HOME/.local/flyway"

    if [ -d "$install_dir" ]; then
        print_info "Flyway installation found at $install_dir"
        export PATH="$install_dir:$PATH"
        return 0
    fi

    print_info "Downloading Flyway ${FLYWAY_VERSION}..."
    mkdir -p "$install_dir"

    curl -L "$FLYWAY_URL" -o "/tmp/flyway.tar.gz"
    tar -xzf "/tmp/flyway.tar.gz" -C "/tmp"

    mv "/tmp/flyway-${FLYWAY_VERSION}"/* "$install_dir/"
    chmod +x "$install_dir/flyway"

    rm -rf "/tmp/flyway.tar.gz" "/tmp/flyway-${FLYWAY_VERSION}"

    export PATH="$install_dir:$PATH"
    print_success "Flyway installed successfully"
}

# Function to load environment configuration
load_env_config() {
    case "$ENVIRONMENT" in
        dev)
            export DB_HOST="${DB_HOST:-localhost}"
            export DB_PORT="${DB_PORT:-5432}"
            export DB_NAME="${DB_NAME:-aswa}"
            export DB_USER="${DB_USER:-aswa}"
            export DB_PASSWORD="${DB_PASSWORD:-aswa_dev_password}"
            ;;
        test)
            if [ -z "$DB_HOST" ] || [ -z "$DB_PASSWORD" ]; then
                print_error "Test environment requires DB_HOST and DB_PASSWORD to be set"
                exit 1
            fi
            export DB_PORT="${DB_PORT:-5432}"
            export DB_NAME="${DB_NAME:-aswa_test}"
            export DB_USER="${DB_USER:-aswa}"
            ;;
        prod)
            if [ -z "$DB_HOST" ] || [ -z "$DB_PASSWORD" ]; then
                print_error "Production environment requires DB_HOST and DB_PASSWORD to be set"
                exit 1
            fi
            export DB_PORT="${DB_PORT:-5432}"
            export DB_NAME="${DB_NAME:-aswa}"
            export DB_USER="${DB_USER:-aswa}"

            # Safety check for production
            if [ "$COMMAND" == "clean" ]; then
                print_error "CLEAN command is disabled in production for safety"
                exit 1
            fi
            ;;
        *)
            print_error "Unknown environment: $ENVIRONMENT"
            print_info "Valid environments: dev, test, prod"
            exit 1
            ;;
    esac

    export FLYWAY_URL="jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}"
    export FLYWAY_USER="$DB_USER"
    export FLYWAY_PASSWORD="$DB_PASSWORD"
    export FLYWAY_LOCATIONS="filesystem:${MIGRATIONS_DIR}"
}

# Function to show configuration
show_config() {
    print_info "Migration Configuration:"
    echo "  Environment:  $ENVIRONMENT"
    echo "  Host:         $DB_HOST"
    echo "  Port:         $DB_PORT"
    echo "  Database:     $DB_NAME"
    echo "  User:         $DB_USER"
    echo "  Migrations:   $MIGRATIONS_DIR"
    echo ""
}

# Function to run Flyway command
run_flyway() {
    local cmd=$1
    print_info "Running Flyway $cmd..."

    flyway \
        -url="$FLYWAY_URL" \
        -user="$FLYWAY_USER" \
        -password="$FLYWAY_PASSWORD" \
        -locations="$FLYWAY_LOCATIONS" \
        -table="schema_version" \
        -validateMigrationNaming=true \
        -outOfOrder=false \
        "$cmd"
}

# Main execution
main() {
    print_info "ASWA Database Migration Tool"
    echo ""

    # Check prerequisites
    check_flyway

    # Load environment configuration
    load_env_config

    # Show configuration
    show_config

    # Confirm for production
    if [ "$ENVIRONMENT" == "prod" ]; then
        print_warning "You are about to run migrations in PRODUCTION"
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            print_info "Migration cancelled"
            exit 0
        fi
    fi

    # Run Flyway command
    case "$COMMAND" in
        migrate)
            run_flyway migrate
            print_success "Migration completed successfully"
            ;;
        info)
            run_flyway info
            ;;
        validate)
            run_flyway validate
            print_success "Validation completed successfully"
            ;;
        clean)
            if [ "$ENVIRONMENT" == "dev" ]; then
                print_warning "This will drop ALL objects in the database!"
                read -p "Are you sure? (yes/no): " confirm
                if [ "$confirm" == "yes" ]; then
                    run_flyway clean
                    print_success "Database cleaned"
                else
                    print_info "Clean cancelled"
                fi
            else
                print_error "CLEAN command is only allowed in dev environment"
                exit 1
            fi
            ;;
        baseline)
            run_flyway baseline
            print_success "Database baselined"
            ;;
        repair)
            run_flyway repair
            print_success "Schema history repaired"
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            echo ""
            echo "Available commands:"
            echo "  migrate   - Run pending migrations"
            echo "  info      - Show migration status"
            echo "  validate  - Validate migrations"
            echo "  clean     - Drop all objects (dev only)"
            echo "  baseline  - Baseline existing database"
            echo "  repair    - Repair schema history table"
            exit 1
            ;;
    esac
}

# Run main function
main
