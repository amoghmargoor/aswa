#!/bin/bash
# Run all tests across all services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python services with their extras
PYTHON_SERVICES=(
  "services/agent-service"
  "services/notification-service"
  "services/integration-service"
  "services/slack-bot"
  "services/teams-bot"
  "services/insight-engine"
)

FAILED_SERVICES=()
PASSED_SERVICES=()

echo "============================================"
echo "Running tests for all services"
echo "============================================"
echo ""

# Run Python service tests
for svc in "${PYTHON_SERVICES[@]}"; do
  if [ -d "$svc" ]; then
    echo "=== Testing $svc ==="
    cd "$svc"

    # Install dependencies with dev extras
    # Try different formats for optional dependencies
    if grep -q '\[tool.poetry.extras\]' pyproject.toml 2>/dev/null; then
      poetry install --extras dev --quiet 2>/dev/null || poetry install --quiet
    elif grep -q '\[project.optional-dependencies\]' pyproject.toml 2>/dev/null; then
      poetry install --with dev --quiet 2>/dev/null || poetry install --all-extras --quiet 2>/dev/null || poetry install --quiet
    else
      poetry install --quiet
    fi

    # Run tests
    if poetry run pytest -v; then
      PASSED_SERVICES+=("$svc")
    else
      FAILED_SERVICES+=("$svc")
    fi

    cd "$SCRIPT_DIR"
    echo ""
  else
    echo "Warning: $svc not found, skipping..."
  fi
done

# Run web-dashboard tests (npm/vitest)
if [ -d "services/web-dashboard" ]; then
  echo "=== Testing services/web-dashboard ==="
  cd services/web-dashboard

  npm install --silent
  if npm test -- --run; then
    PASSED_SERVICES+=("services/web-dashboard")
  else
    FAILED_SERVICES+=("services/web-dashboard")
  fi

  cd "$SCRIPT_DIR"
  echo ""
fi

# Summary
echo "============================================"
echo "Test Summary"
echo "============================================"
echo ""
echo "Passed: ${#PASSED_SERVICES[@]}"
for svc in "${PASSED_SERVICES[@]}"; do
  echo "  ✓ $svc"
done

if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
  echo ""
  echo "Failed: ${#FAILED_SERVICES[@]}"
  for svc in "${FAILED_SERVICES[@]}"; do
    echo "  ✗ $svc"
  done
  exit 1
else
  echo ""
  echo "All tests passed!"
  exit 0
fi
