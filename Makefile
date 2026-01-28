.PHONY: help setup build test test-java test-python lint format clean docker-build docker-push helm-lint
.PHONY: up down logs status shell db-migrate db-seed db-reset api-client

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(BLUE)ASWA - AI-driven insight aggregation platform$(NC)'
	@echo ''
	@echo '$(GREEN)Available targets:$(NC)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ''

setup: ## Install all dependencies (Gradle, Poetry, pre-commit)
	@./scripts/dev.sh setup

build: ## Build all services (Java and Python)
	@echo "$(BLUE)Building all services...$(NC)"
	@echo "$(GREEN)Building Java services...$(NC)"
	./gradlew build -x test
	@echo "$(GREEN)Building Python services...$(NC)"
	poetry build
	@echo "$(GREEN)Build complete!$(NC)"

test: test-java test-python ## Run all tests with coverage

test-java: ## Run Java tests only
	@echo "$(BLUE)Running Java tests...$(NC)"
	./gradlew testAll jacocoTestReport
	@echo "$(GREEN)Java tests complete!$(NC)"

test-python: ## Run Python tests only
	@echo "$(BLUE)Running Python tests...$(NC)"
	poetry run pytest --cov --cov-report=html --cov-report=term
	@echo "$(GREEN)Python tests complete!$(NC)"

test-ingestion: ## Run ingestion service tests
	@./scripts/dev.sh test ingestion

test-query: ## Run query service tests
	@./scripts/dev.sh test query

test-insight: ## Run insight service tests
	@./scripts/dev.sh test insight

test-web: ## Run web dashboard tests
	@./scripts/dev.sh test web

lint: ## Run all linters (Java and Python)
	@echo "$(BLUE)Running linters...$(NC)"
	@echo "$(GREEN)Checking Java code formatting...$(NC)"
	./gradlew lintAll
	@echo "$(GREEN)Checking Python code with Ruff...$(NC)"
	poetry run ruff check .
	@echo "$(GREEN)Checking Python types with Mypy...$(NC)"
	poetry run mypy .
	@echo "$(GREEN)Lint checks complete!$(NC)"

format: ## Format all code (Java and Python)
	@echo "$(BLUE)Formatting code...$(NC)"
	@echo "$(GREEN)Formatting Java code...$(NC)"
	./gradlew formatAll
	@echo "$(GREEN)Formatting Python code...$(NC)"
	poetry run black .
	poetry run ruff check --fix .
	@echo "$(GREEN)Formatting complete!$(NC)"

clean: ## Clean all build artifacts
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	./gradlew cleanAll
	poetry env remove --all 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "$(GREEN)Clean complete!$(NC)"

docker-build: ## Build all Docker images
	@./scripts/dev.sh build

docker-push: ## Push Docker images to registry
	@echo "$(BLUE)Pushing Docker images...$(NC)"
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "$(YELLOW)Warning: DOCKER_REGISTRY not set. Set it with: export DOCKER_REGISTRY=<your-registry>$(NC)"; \
		exit 1; \
	fi
	docker-compose -f infrastructure/docker/docker-compose.yaml push
	@echo "$(GREEN)Docker images pushed!$(NC)"

helm-lint: ## Lint Helm charts
	@echo "$(BLUE)Linting Helm charts...$(NC)"
	@if [ ! -d infrastructure/helm ]; then \
		echo "$(YELLOW)Warning: infrastructure/helm not found. Skipping Helm lint.$(NC)"; \
		exit 0; \
	fi
	@for chart in infrastructure/helm/*/; do \
		if [ -f "$$chart/Chart.yaml" ]; then \
			echo "$(GREEN)Linting $$chart...$(NC)"; \
			helm lint "$$chart"; \
		fi; \
	done
	@echo "$(GREEN)Helm lint complete!$(NC)"

# Development environment commands
up: ## Start local development environment
	@./scripts/dev.sh up

down: ## Stop local development environment
	@./scripts/dev.sh down

restart: ## Restart development environment
	@./scripts/dev.sh restart

logs: ## Show logs from development environment
	@./scripts/dev.sh logs

status: ## Show status of all services
	@./scripts/dev.sh status

shell: ## Open shell in service (usage: make shell SERVICE=api-gateway)
	@./scripts/dev.sh shell $(SERVICE)

# Database commands
db-migrate: ## Run database migrations
	@./scripts/dev.sh db migrate

db-seed: ## Seed test data
	@./scripts/dev.sh db seed

db-reset: ## Reset database (destructive!)
	@./scripts/dev.sh db reset

db-shell: ## Open PostgreSQL shell
	@./scripts/dev.sh db shell

redis-shell: ## Open Redis CLI
	@./scripts/dev.sh shell redis

# API client generation
api-client: ## Generate API client from OpenAPI spec
	@./scripts/generate-api-client.sh

# Convenience aliases
dev-up: up
dev-down: down
dev-logs: logs
dev-status: status
dev-restart: restart
dev-clean: ## Stop and remove all data (WARNING: deletes volumes)
	@./scripts/dev.sh clean

check-deps: ## Check for outdated dependencies
	@echo "$(BLUE)Checking for outdated dependencies...$(NC)"
	@echo "$(GREEN)Checking Gradle dependencies...$(NC)"
	./gradlew dependencyUpdates
	@echo "$(GREEN)Checking Python dependencies...$(NC)"
	poetry show --outdated
	@echo "$(GREEN)Dependency check complete!$(NC)"
