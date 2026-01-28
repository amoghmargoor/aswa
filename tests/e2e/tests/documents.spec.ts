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
