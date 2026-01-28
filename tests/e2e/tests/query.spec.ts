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
