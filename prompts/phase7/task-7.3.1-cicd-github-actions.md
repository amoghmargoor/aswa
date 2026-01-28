# Task 7.3.1: CI/CD - GitHub Actions Setup

## Context

You are setting up CI/CD for ASWA at `/.github/workflows/`. This task focuses on the base GitHub Actions configuration and reusable workflows.

## Objective

Create GitHub Actions configurations that:
1. Define reusable workflows
2. Configure environment settings
3. Set up caching strategies
4. Manage secrets securely
5. Support multiple environments

## Requirements

### 1. Create `/.github/workflows/ci.yaml`
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

permissions:
  contents: read
  packages: write
  id-token: write

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: ${{ github.repository_owner }}/aswa

jobs:
  changes:
    name: Detect Changes
    runs-on: ubuntu-latest
    outputs:
      api-gateway: ${{ steps.filter.outputs.api-gateway }}
      ingestion-service: ${{ steps.filter.outputs.ingestion-service }}
      query-service: ${{ steps.filter.outputs.query-service }}
      insight-service: ${{ steps.filter.outputs.insight-service }}
      web-dashboard: ${{ steps.filter.outputs.web-dashboard }}
      common-java: ${{ steps.filter.outputs.common-java }}
      common-python: ${{ steps.filter.outputs.common-python }}
      infrastructure: ${{ steps.filter.outputs.infrastructure }}
    steps:
      - uses: actions/checkout@v4

      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api-gateway:
              - 'services/api-gateway/**'
              - 'libs/common-java/**'
            ingestion-service:
              - 'services/ingestion-service/**'
              - 'libs/common-python/**'
            query-service:
              - 'services/query-service/**'
              - 'libs/common-python/**'
            insight-service:
              - 'services/insight-service/**'
              - 'libs/common-python/**'
            web-dashboard:
              - 'services/web-dashboard/**'
            common-java:
              - 'libs/common-java/**'
            common-python:
              - 'libs/common-python/**'
            infrastructure:
              - 'infrastructure/**'
              - '.github/workflows/**'

  lint:
    name: Lint
    runs-on: ubuntu-latest
    needs: changes
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Set up Java
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Python linters
        run: |
          pip install ruff mypy

      - name: Lint Python code
        if: needs.changes.outputs.common-python == 'true' || needs.changes.outputs.ingestion-service == 'true' || needs.changes.outputs.query-service == 'true' || needs.changes.outputs.insight-service == 'true'
        run: |
          ruff check services/ libs/common-python/
          ruff format --check services/ libs/common-python/

      - name: Lint Java code
        if: needs.changes.outputs.common-java == 'true' || needs.changes.outputs.api-gateway == 'true'
        working-directory: services/api-gateway
        run: |
          ./gradlew spotlessCheck

      - name: Lint TypeScript code
        if: needs.changes.outputs.web-dashboard == 'true'
        working-directory: services/web-dashboard
        run: |
          npm ci
          npm run lint

  build-java:
    name: Build Java Services
    runs-on: ubuntu-latest
    needs: [changes, lint]
    if: needs.changes.outputs.api-gateway == 'true' || needs.changes.outputs.common-java == 'true'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Java
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'
          cache: 'gradle'

      - name: Build common-java
        working-directory: libs/common-java
        run: |
          ./gradlew build publishToMavenLocal

      - name: Build API Gateway
        working-directory: services/api-gateway
        run: |
          ./gradlew build -x test

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: java-builds
          path: |
            services/api-gateway/build/libs/*.jar
          retention-days: 1

  build-python:
    name: Build Python Services
    runs-on: ubuntu-latest
    needs: [changes, lint]
    strategy:
      matrix:
        service:
          - ingestion-service
          - query-service
          - insight-service
    if: needs.changes.outputs.ingestion-service == 'true' || needs.changes.outputs.query-service == 'true' || needs.changes.outputs.insight-service == 'true' || needs.changes.outputs.common-python == 'true'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        working-directory: services/${{ matrix.service }}
        run: |
          pip install -e ../../libs/common-python
          pip install -e ".[dev]"

      - name: Type check
        working-directory: services/${{ matrix.service }}
        run: |
          mypy src/ --ignore-missing-imports

  build-web:
    name: Build Web Dashboard
    runs-on: ubuntu-latest
    needs: [changes, lint]
    if: needs.changes.outputs.web-dashboard == 'true'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: services/web-dashboard/package-lock.json

      - name: Install dependencies
        working-directory: services/web-dashboard
        run: npm ci

      - name: Build
        working-directory: services/web-dashboard
        run: npm run build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: web-build
          path: services/web-dashboard/dist
          retention-days: 1

  test:
    name: Test
    uses: ./.github/workflows/test.yaml
    needs: [build-java, build-python, build-web]
    if: always() && !cancelled()
    secrets: inherit

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: [build-java, build-python, build-web]
    if: always() && !cancelled()
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Run Snyk security scan
        uses: snyk/actions/python@master
        continue-on-error: true
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high
```

### 2. Create `/.github/workflows/test.yaml`
```yaml
name: Test

on:
  workflow_call:
    secrets:
      CODECOV_TOKEN:
        required: false

jobs:
  test-java:
    name: Test Java
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: aswa
          POSTGRES_PASSWORD: aswa
          POSTGRES_DB: aswa_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Java
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'
          cache: 'gradle'

      - name: Build common-java
        working-directory: libs/common-java
        run: ./gradlew build publishToMavenLocal

      - name: Test API Gateway
        working-directory: services/api-gateway
        env:
          DATABASE_URL: postgresql://aswa:aswa@localhost:5432/aswa_test
          REDIS_URL: redis://localhost:6379
        run: |
          ./gradlew test jacocoTestReport

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: services/api-gateway/build/reports/jacoco/test/jacocoTestReport.xml
          flags: java
          fail_ci_if_error: false

  test-python:
    name: Test Python
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service:
          - ingestion-service
          - query-service
          - insight-service
      fail-fast: false
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: aswa
          POSTGRES_PASSWORD: aswa
          POSTGRES_DB: aswa_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      elasticsearch:
        image: elasticsearch:8.11.0
        env:
          discovery.type: single-node
          xpack.security.enabled: false
        ports:
          - 9200:9200
        options: >-
          --health-cmd "curl -f http://localhost:9200/_cluster/health"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 10

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        working-directory: services/${{ matrix.service }}
        run: |
          pip install -e ../../libs/common-python
          pip install -e ".[dev]"

      - name: Run tests
        working-directory: services/${{ matrix.service }}
        env:
          DATABASE_URL: postgresql://aswa:aswa@localhost:5432/aswa_test
          REDIS_URL: redis://localhost:6379
          ELASTICSEARCH_URL: http://localhost:9200
        run: |
          pytest tests/ -v --cov=src --cov-report=xml --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: services/${{ matrix.service }}/coverage.xml
          flags: python,${{ matrix.service }}
          fail_ci_if_error: false

  test-web:
    name: Test Web Dashboard
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: services/web-dashboard/package-lock.json

      - name: Install dependencies
        working-directory: services/web-dashboard
        run: npm ci

      - name: Run tests
        working-directory: services/web-dashboard
        run: npm run test:coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: services/web-dashboard/coverage/lcov.info
          flags: typescript,web
          fail_ci_if_error: false

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: [test-java, test-python]
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: aswa
          POSTGRES_PASSWORD: aswa
          POSTGRES_DB: aswa_test
        ports:
          - 5432:5432

      redis:
        image: redis:7
        ports:
          - 6379:6379

      elasticsearch:
        image: elasticsearch:8.11.0
        env:
          discovery.type: single-node
          xpack.security.enabled: false
        ports:
          - 9200:9200

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Set up Java
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'

      - name: Start services
        run: |
          # Build and start services for integration testing
          docker-compose -f docker-compose.test.yml up -d --build
          sleep 30

      - name: Run integration tests
        run: |
          pip install pytest httpx
          pytest tests/integration/ -v

      - name: Cleanup
        if: always()
        run: docker-compose -f docker-compose.test.yml down -v
```

### 3. Create `/.github/workflows/build-images.yaml`
```yaml
name: Build Images

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      tag:
        required: true
        type: string
    outputs:
      images:
        description: "Built image tags"
        value: ${{ jobs.build.outputs.images }}

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: ${{ github.repository_owner }}/aswa

jobs:
  build:
    name: Build Docker Images
    runs-on: ubuntu-latest
    outputs:
      images: ${{ steps.output.outputs.images }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        run: |
          echo "sha_short=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT
          echo "date=$(date +'%Y%m%d')" >> $GITHUB_OUTPUT

      - name: Build and push API Gateway
        uses: docker/build-push-action@v5
        with:
          context: .
          file: services/api-gateway/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/api-gateway:${{ inputs.tag }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/api-gateway:${{ steps.meta.outputs.sha_short }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            BUILD_DATE=${{ steps.meta.outputs.date }}
            VERSION=${{ inputs.tag }}
            COMMIT=${{ github.sha }}

      - name: Build and push Ingestion Service
        uses: docker/build-push-action@v5
        with:
          context: .
          file: services/ingestion-service/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/ingestion-service:${{ inputs.tag }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/ingestion-service:${{ steps.meta.outputs.sha_short }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push Query Service
        uses: docker/build-push-action@v5
        with:
          context: .
          file: services/query-service/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/query-service:${{ inputs.tag }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/query-service:${{ steps.meta.outputs.sha_short }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push Insight Service
        uses: docker/build-push-action@v5
        with:
          context: .
          file: services/insight-service/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/insight-service:${{ inputs.tag }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/insight-service:${{ steps.meta.outputs.sha_short }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push Web Dashboard
        uses: docker/build-push-action@v5
        with:
          context: services/web-dashboard
          file: services/web-dashboard/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/web-dashboard:${{ inputs.tag }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/web-dashboard:${{ steps.meta.outputs.sha_short }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Output image tags
        id: output
        run: |
          cat >> $GITHUB_OUTPUT << EOF
          images<<IMAGES_EOF
          {
            "api-gateway": "${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/api-gateway:${{ inputs.tag }}",
            "ingestion-service": "${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/ingestion-service:${{ inputs.tag }}",
            "query-service": "${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/query-service:${{ inputs.tag }}",
            "insight-service": "${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/insight-service:${{ inputs.tag }}",
            "web-dashboard": "${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/web-dashboard:${{ inputs.tag }}"
          }
          IMAGES_EOF
          EOF
```

### 4. Create `/.github/dependabot.yml`
```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/libs/common-python"
    schedule:
      interval: "weekly"
    groups:
      python-minor:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"

  - package-ecosystem: "pip"
    directory: "/services/ingestion-service"
    schedule:
      interval: "weekly"
    groups:
      python-minor:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"

  - package-ecosystem: "pip"
    directory: "/services/query-service"
    schedule:
      interval: "weekly"

  - package-ecosystem: "pip"
    directory: "/services/insight-service"
    schedule:
      interval: "weekly"

  # Gradle dependencies
  - package-ecosystem: "gradle"
    directory: "/libs/common-java"
    schedule:
      interval: "weekly"

  - package-ecosystem: "gradle"
    directory: "/services/api-gateway"
    schedule:
      interval: "weekly"

  # npm dependencies
  - package-ecosystem: "npm"
    directory: "/services/web-dashboard"
    schedule:
      interval: "weekly"
    groups:
      npm-minor:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"

  # Docker dependencies
  - package-ecosystem: "docker"
    directory: "/services/api-gateway"
    schedule:
      interval: "weekly"

  - package-ecosystem: "docker"
    directory: "/services/ingestion-service"
    schedule:
      interval: "weekly"

  - package-ecosystem: "docker"
    directory: "/services/web-dashboard"
    schedule:
      interval: "weekly"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      actions-minor:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"
```

## Verification

1. Commit workflow files to repository
2. Trigger CI workflow: `git push origin develop`
3. Verify all jobs pass in GitHub Actions
4. Check code coverage reports in Codecov
5. Verify security scan results
