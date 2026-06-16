// Story: 269
import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

test.describe('269: Scanner', () => {
  test.beforeEach(async ({ page }) => {
    // Pre-req: User has the Gap Forecaster open
    // Launch the Gap Forecaster
    await page.goto(BASE_URL);
    // Expected: The Scanner tab is shown (implied by the main heading being visible)
    await expect(page.getByRole('heading', { name: 'Gap Forecaster' })).toBeVisible();
  });

  test('269-AC1: Scanner / Run pre-market scan', async ({ page }) => {
    // Click the Scan button
    await page.getByRole('button', { name: 'Scan', exact: true }).click();
    // Expected: The results table with a Ticker column is visible
    await expect(page.getByRole('columnheader', { name: 'Ticker' })).toBeVisible();
    // Verify the top pick heading is shown
    // Expected: The Gap Forecaster heading is visible (more specific: Pre-market scan heading)
    await expect(page.getByRole('heading', { name: 'Pre-market scan · 2026-06-16' })).toBeVisible();
  });

  test('269-AC5: Navigation / Switch to Journal tab', async ({ page }) => {
    // Click the Journal tab
    await page.getByRole('button', { name: 'Journal' }).click();
    // Expected: The Trade journal heading is visible
    await expect(page.getByRole('heading', { name: 'Trade journal' })).toBeVisible();
  });
});