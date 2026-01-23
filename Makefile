.PHONY: help setup build test test-java test-python lint format clean docker-build docker-push helm-lint

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
	@echo "$(BLUE)Installing dependencies...$(NC)"
	@if ! command -v java >/dev/null 2>&1; then \
		echo "$(YELLOW)Warning: Java 21 not found. Please install Java 21.$(NC)"; \
	fi
	@if ! command -v python3 >/dev/null 2>&1; then \
		echo "$(YELLOW)Warning: Python 3.11+ not found. Please install Python 3.11+.$(NC)"; \
	fi
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "$(YELLOW)Installing Poetry...$(NC)"; \
		curl -sSL https://install.python-poetry.org | python3 -; \
	fi
	@echo "$(GREEN)Installing Python dependencies...$(NC)"
	poetry install --no-root
	@echo "$(GREEN)Installing pre-commit hooks...$(NC)"
	poetry run pre-commit install
	@echo "$(GREEN)Setup complete!$(NC)"

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
	@echo "$(BLUE)Building Docker images...$(NC)"
	@if [ ! -f docker-compose.yml ]; then \
		echo "$(YELLOW)Warning: docker-compose.yml not found. Skipping Docker build.$(NC)"; \
		exit 0; \
	fi
	docker-compose build
	@echo "$(GREEN)Docker images built!$(NC)"

docker-push: ## Push Docker images to registry
	@echo "$(BLUE)Pushing Docker images...$(NC)"
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "$(YELLOW)Warning: DOCKER_REGISTRY not set. Set it with: export DOCKER_REGISTRY=<your-registry>$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f docker-compose.yml ]; then \
		echo "$(YELLOW)Warning: docker-compose.yml not found. Skipping Docker push.$(NC)"; \
		exit 0; \
	fi
	docker-compose push
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

dev-up: ## Start local development environment (Docker Compose)
	@echo "$(BLUE)Starting development environment...$(NC)"
	@if [ ! -f docker-compose.yml ]; then \
		echo "$(YELLOW)Warning: docker-compose.yml not found.$(NC)"; \
		exit 1; \
	fi
	docker-compose up -d
	@echo "$(GREEN)Development environment started!$(NC)"
	@echo ""
	@echo "$(BLUE)Services:$(NC)"
	@echo "  PostgreSQL:      localhost:5432"
	@echo "  Redis:           localhost:6379"
	@echo "$(YELLOW)To start API Gateway: make dev-services$(NC)"
	@echo "$(YELLOW)To start management tools: make dev-tools$(NC)"

dev-services: ## Start development environment with all services
	@echo "$(BLUE)Starting development environment with services...$(NC)"
	docker-compose --profile services up -d
	@echo "$(GREEN)All services started!$(NC)"
	@echo ""
	@echo "$(BLUE)Services:$(NC)"
	@echo "  API Gateway:     http://localhost:8080"
	@echo "  Health:          http://localhost:8080/health"
	@echo "  Swagger UI:      http://localhost:8080/swagger-ui.html"

dev-tools: ## Start development environment with management tools
	@echo "$(BLUE)Starting management tools...$(NC)"
	docker-compose --profile tools up -d
	@echo "$(GREEN)Management tools started!$(NC)"
	@echo ""
	@echo "$(BLUE)Tools:$(NC)"
	@echo "  PgAdmin:         http://localhost:5050"
	@echo "  Redis Commander: http://localhost:8081"

dev-all: ## Start everything (core + services + tools)
	@echo "$(BLUE)Starting all services and tools...$(NC)"
	docker-compose --profile services --profile tools up -d
	@echo "$(GREEN)Everything started!$(NC)"

dev-down: ## Stop local development environment
	@echo "$(BLUE)Stopping development environment...$(NC)"
	@if [ ! -f docker-compose.yml ]; then \
		echo "$(YELLOW)Warning: docker-compose.yml not found.$(NC)"; \
		exit 0; \
	fi
	docker-compose down
	@echo "$(GREEN)Development environment stopped!$(NC)"

dev-restart: ## Restart development environment
	@echo "$(BLUE)Restarting development environment...$(NC)"
	$(MAKE) dev-down
	$(MAKE) dev-up

dev-logs: ## Show logs from development environment
	@if [ ! -f docker-compose.yml ]; then \
		echo "$(YELLOW)Warning: docker-compose.yml not found.$(NC)"; \
		exit 1; \
	fi
	docker-compose logs -f

dev-status: ## Show status of all services
	@if [ ! -f docker-compose.yml ]; then \
		echo "$(YELLOW)Warning: docker-compose.yml not found.$(NC)"; \
		exit 1; \
	fi
	docker-compose ps

dev-clean: ## Stop and remove all data (WARNING: deletes volumes)
	@echo "$(YELLOW)WARNING: This will delete all Docker volumes and data!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ]
	docker-compose down -v
	@echo "$(GREEN)All data cleaned!$(NC)"

db-shell: ## Open PostgreSQL shell
	@docker exec -it aswa-postgres psql -U aswa -d aswa

redis-shell: ## Open Redis CLI
	@docker exec -it aswa-redis redis-cli -a aswa_dev_password

db-migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(NC)"
	@if [ -f scripts/db-migrate.sh ]; then \
		./scripts/db-migrate.sh migrate dev; \
	else \
		echo "$(YELLOW)Migration script not found.$(NC)"; \
	fi

check-deps: ## Check for outdated dependencies
	@echo "$(BLUE)Checking for outdated dependencies...$(NC)"
	@echo "$(GREEN)Checking Gradle dependencies...$(NC)"
	./gradlew dependencyUpdates
	@echo "$(GREEN)Checking Python dependencies...$(NC)"
	poetry show --outdated
	@echo "$(GREEN)Dependency check complete!$(NC)"
