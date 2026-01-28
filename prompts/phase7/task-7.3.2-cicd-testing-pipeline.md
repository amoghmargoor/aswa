# Task 7.3.2: CI/CD - Testing Pipeline

## Context

You are setting up CI/CD for ASWA at `/.github/workflows/`. Base workflows are complete. Now we need comprehensive testing pipelines.

## Objective

Create testing pipelines that:
1. Run unit tests with coverage
2. Execute integration tests
3. Perform end-to-end testing
4. Generate test reports
5. Enforce quality gates

## Requirements

### 1. Create `/.github/workflows/e2e-tests.yaml`
```yaml
name: E2E Tests

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to test'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production

jobs:
  e2e:
    name: End-to-End Tests
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: tests/e2e/package-lock.json

      - name: Install dependencies
        working-directory: tests/e2e
        run: npm ci

      - name: Install Playwright browsers
        working-directory: tests/e2e
        run: npx playwright install --with-deps

      - name: Run E2E tests
        working-directory: tests/e2e
        env:
          BASE_URL: ${{ vars.E2E_BASE_URL }}
          API_URL: ${{ vars.E2E_API_URL }}
          TEST_USER_EMAIL: ${{ secrets.E2E_TEST_USER_EMAIL }}
          TEST_USER_PASSWORD: ${{ secrets.E2E_TEST_USER_PASSWORD }}
        run: |
          npx playwright test --reporter=html,github

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report-${{ inputs.environment }}
          path: tests/e2e/playwright-report/
          retention-days: 30

      - name: Upload test videos
        uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-videos-${{ inputs.environment }}
          path: tests/e2e/test-results/
          retention-days: 7

  api-e2e:
    name: API E2E Tests
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        working-directory: tests/api-e2e
        run: |
          pip install -r requirements.txt

      - name: Run API E2E tests
        working-directory: tests/api-e2e
        env:
          API_URL: ${{ vars.E2E_API_URL }}
          API_TOKEN: ${{ secrets.E2E_API_TOKEN }}
        run: |
          pytest tests/ -v --html=report.html --self-contained-html

      - name: Upload test report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: api-e2e-report-${{ inputs.environment }}
          path: tests/api-e2e/report.html
          retention-days: 30
```

### 2. Create `/tests/e2e/playwright.config.ts`
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['github'],
    ['json', { outputFile: 'test-results.json' }],
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
});
```

### 3. Create `/tests/e2e/tests/auth.spec.ts`
```typescript
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('should display login page', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('should show validation errors for empty form', async ({ page }) => {
    await page.goto('/login');

    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/email is required/i)).toBeVisible();
    await expect(page.getByText(/password is required/i)).toBeVisible();
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.getByLabel(/email/i).fill(process.env.TEST_USER_EMAIL!);
    await page.getByLabel(/password/i).fill(process.env.TEST_USER_PASSWORD!);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL('/dashboard');
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.getByLabel(/email/i).fill('invalid@example.com');
    await page.getByLabel(/password/i).fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/invalid credentials/i)).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel(/email/i).fill(process.env.TEST_USER_EMAIL!);
    await page.getByLabel(/password/i).fill(process.env.TEST_USER_PASSWORD!);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL('/dashboard');

    // Logout
    await page.getByRole('button', { name: /user menu/i }).click();
    await page.getByRole('menuitem', { name: /logout/i }).click();

    await expect(page).toHaveURL('/login');
  });
});
```

### 4. Create `/tests/e2e/tests/documents.spec.ts`
```typescript
import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Document Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.getByLabel(/email/i).fill(process.env.TEST_USER_EMAIL!);
    await page.getByLabel(/password/i).fill(process.env.TEST_USER_PASSWORD!);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL('/dashboard');
  });

  test('should display documents list', async ({ page }) => {
    await page.goto('/documents');

    await expect(page.getByRole('heading', { name: /documents/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /upload/i })).toBeVisible();
  });

  test('should upload a document', async ({ page }) => {
    await page.goto('/documents');

    // Click upload button
    await page.getByRole('button', { name: /upload/i }).click();

    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures', 'test-document.pdf'));

    // Wait for upload to complete
    await expect(page.getByText(/upload complete/i)).toBeVisible({ timeout: 30000 });

    // Verify document appears in list
    await expect(page.getByText('test-document.pdf')).toBeVisible();
  });

  test('should show document processing status', async ({ page }) => {
    await page.goto('/documents');

    // Upload a document
    await page.getByRole('button', { name: /upload/i }).click();
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures', 'test-document.pdf'));

    // Check for processing status
    await expect(page.getByText(/processing/i)).toBeVisible({ timeout: 10000 });

    // Wait for processing to complete
    await expect(page.getByText(/processed/i)).toBeVisible({ timeout: 120000 });
  });

  test('should view document details', async ({ page }) => {
    await page.goto('/documents');

    // Click on first document
    await page.getByRole('row').nth(1).click();

    // Verify document details page
    await expect(page.getByRole('heading', { name: /document details/i })).toBeVisible();
    await expect(page.getByText(/insights/i)).toBeVisible();
  });

  test('should delete a document', async ({ page }) => {
    await page.goto('/documents');

    // Get document name
    const documentName = await page.getByRole('row').nth(1).getByRole('cell').first().textContent();

    // Click delete button
    await page.getByRole('row').nth(1).getByRole('button', { name: /delete/i }).click();

    // Confirm deletion
    await page.getByRole('button', { name: /confirm/i }).click();

    // Verify document is removed
    await expect(page.getByText(documentName!)).not.toBeVisible();
  });
});
```

### 5. Create `/tests/e2e/tests/query.spec.ts`
```typescript
import { test, expect } from '@playwright/test';

test.describe('Query Interface', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel(/email/i).fill(process.env.TEST_USER_EMAIL!);
    await page.getByLabel(/password/i).fill(process.env.TEST_USER_PASSWORD!);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL('/dashboard');
  });

  test('should display query interface', async ({ page }) => {
    await page.goto('/query');

    await expect(page.getByRole('heading', { name: /ask/i })).toBeVisible();
    await expect(page.getByPlaceholder(/ask a question/i)).toBeVisible();
  });

  test('should submit a query and receive response', async ({ page }) => {
    await page.goto('/query');

    // Enter query
    await page.getByPlaceholder(/ask a question/i).fill('What are the main risks in the documents?');
    await page.getByRole('button', { name: /ask/i }).click();

    // Wait for response
    await expect(page.getByTestId('query-response')).toBeVisible({ timeout: 60000 });

    // Verify response has content
    const response = await page.getByTestId('query-response').textContent();
    expect(response?.length).toBeGreaterThan(50);
  });

  test('should display citations in response', async ({ page }) => {
    await page.goto('/query');

    await page.getByPlaceholder(/ask a question/i).fill('Summarize the key findings');
    await page.getByRole('button', { name: /ask/i }).click();

    // Wait for response with citations
    await expect(page.getByTestId('citations')).toBeVisible({ timeout: 60000 });

    // Verify at least one citation exists
    const citations = page.getByTestId('citation');
    await expect(citations.first()).toBeVisible();
  });

  test('should show query history', async ({ page }) => {
    await page.goto('/query');

    // Submit a query
    await page.getByPlaceholder(/ask a question/i).fill('Test query');
    await page.getByRole('button', { name: /ask/i }).click();
    await expect(page.getByTestId('query-response')).toBeVisible({ timeout: 60000 });

    // Check query history
    await page.getByRole('button', { name: /history/i }).click();
    await expect(page.getByText('Test query')).toBeVisible();
  });
});
```

### 6. Create `/tests/api-e2e/tests/test_api_health.py`
```python
import pytest
import httpx
import os

API_URL = os.environ.get("API_URL", "http://localhost:8000")


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_api_gateway_health(self):
        """Test API gateway health endpoint."""
        response = httpx.get(f"{API_URL}/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_gateway_ready(self):
        """Test API gateway readiness endpoint."""
        response = httpx.get(f"{API_URL}/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True

    def test_api_gateway_metrics(self):
        """Test API gateway metrics endpoint."""
        response = httpx.get(f"{API_URL}/metrics")

        assert response.status_code == 200
        assert "http_requests_total" in response.text


class TestAPIEndpoints:
    """Test API endpoints."""

    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers."""
        token = os.environ.get("API_TOKEN")
        return {"Authorization": f"Bearer {token}"}

    def test_get_documents(self, auth_headers):
        """Test get documents endpoint."""
        response = httpx.get(
            f"{API_URL}/api/v1/documents",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    def test_get_insights(self, auth_headers):
        """Test get insights endpoint."""
        response = httpx.get(
            f"{API_URL}/api/v1/insights",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    def test_submit_query(self, auth_headers):
        """Test query submission endpoint."""
        response = httpx.post(
            f"{API_URL}/api/v1/query",
            headers=auth_headers,
            json={
                "query": "What are the main topics in the documents?",
            },
            timeout=120.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0

    def test_unauthorized_access(self):
        """Test unauthorized access is rejected."""
        response = httpx.get(f"{API_URL}/api/v1/documents")

        assert response.status_code == 401

    def test_rate_limiting(self, auth_headers):
        """Test rate limiting is enforced."""
        # Make many requests quickly
        for _ in range(150):
            httpx.get(
                f"{API_URL}/api/v1/documents",
                headers=auth_headers,
            )

        # Should get rate limited
        response = httpx.get(
            f"{API_URL}/api/v1/documents",
            headers=auth_headers,
        )

        assert response.status_code == 429
```

### 7. Create `/tests/api-e2e/tests/test_document_flow.py`
```python
import pytest
import httpx
import os
import time
from pathlib import Path

API_URL = os.environ.get("API_URL", "http://localhost:8000")


class TestDocumentFlow:
    """Test complete document processing flow."""

    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers."""
        token = os.environ.get("API_TOKEN")
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def test_file(self, tmp_path):
        """Create a test file."""
        file_path = tmp_path / "test-document.txt"
        file_path.write_text("""
        This is a test document for ASWA.

        It contains some sample text about various topics:

        1. Risk Assessment
        The project has several identified risks including budget overruns,
        timeline delays, and resource constraints.

        2. Opportunities
        There are opportunities for cost savings through automation
        and improved efficiency in the workflow.

        3. Recommendations
        We recommend implementing automated monitoring and establishing
        clear communication channels.
        """)
        return file_path

    def test_upload_document(self, auth_headers, test_file):
        """Test document upload."""
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "test-document.txt"
        assert data["status"] == "pending"

        return data["id"]

    def test_document_processing(self, auth_headers, test_file):
        """Test document processing completes."""
        # Upload document
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Wait for processing to complete
        max_wait = 120
        start = time.time()

        while time.time() - start < max_wait:
            response = httpx.get(
                f"{API_URL}/api/v1/documents/{document_id}",
                headers=auth_headers,
            )

            data = response.json()
            if data["status"] == "processed":
                break
            elif data["status"] == "failed":
                pytest.fail(f"Document processing failed: {data.get('error')}")

            time.sleep(5)
        else:
            pytest.fail("Document processing timed out")

        assert data["status"] == "processed"
        assert data["insight_count"] > 0

    def test_get_document_insights(self, auth_headers, test_file):
        """Test getting insights from a document."""
        # Upload and wait for processing
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Wait for processing
        time.sleep(30)

        # Get insights
        response = httpx.get(
            f"{API_URL}/api/v1/documents/{document_id}/insights",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

        # Check insight structure
        if len(data["items"]) > 0:
            insight = data["items"][0]
            assert "id" in insight
            assert "type" in insight
            assert "title" in insight
            assert "confidence" in insight

    def test_query_document(self, auth_headers, test_file):
        """Test querying about a specific document."""
        # Upload and wait for processing
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Wait for processing
        time.sleep(30)

        # Query about the document
        response = httpx.post(
            f"{API_URL}/api/v1/query",
            headers=auth_headers,
            json={
                "query": "What risks are mentioned in the document?",
                "document_ids": [document_id],
            },
            timeout=120.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "risk" in data["response"].lower() or "budget" in data["response"].lower()

    def test_delete_document(self, auth_headers, test_file):
        """Test document deletion."""
        # Upload document
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Delete document
        response = httpx.delete(
            f"{API_URL}/api/v1/documents/{document_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify document is deleted
        response = httpx.get(
            f"{API_URL}/api/v1/documents/{document_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
```

## Verification

1. Run E2E tests locally: `npx playwright test`
2. Run API E2E tests: `pytest tests/api-e2e/ -v`
3. Verify test reports are generated
4. Check test coverage is adequate
5. Ensure tests pass in CI environment
