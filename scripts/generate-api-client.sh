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
