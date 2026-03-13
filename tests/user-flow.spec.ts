import { test, expect } from '@playwright/test';

test.describe('AI Wealth Monitor Flow', () => {

  test('Should render login page', async ({ page }) => {
    await page.goto('/');
    
    // Should be redirected to login
    await expect(page.getByRole('heading', { name: /AI Wealth Monitor/i })).toBeVisible();
    await expect(page.getByText(/Sign in with Google/i)).toBeVisible();
  });

  test('Should bypass login with demo param and render onboarding', async ({ page }) => {
    // Go directly to onboarding with demo bypass
    await page.goto('/onboarding?demo=true');
    
    // Verify Onboarding Page
    await expect(page.getByRole('heading', { name: /Family Setup/i })).toBeVisible();
    
    // Click Complete Setup
    await page.getByRole('button', { name: /Complete Setup/i }).click();

    // Should navigate to dashboard automatically
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('Should verify dashboard tabs and action items', async ({ page }) => {
    // Bypassing directly to dashboard
    await page.goto('/dashboard?demo=true');

    // Check main title
    await expect(page.getByRole('heading', { name: /Portfolio Overview/i })).toBeVisible();

    // Verify Tabs exist
    const userTab = page.getByRole('button', { name: /My Portfolio/i });
    const spouseTab = page.getByRole('button', { name: /Spouse Portfolio/i });
    const jointTab = page.getByRole('button', { name: /Joint View/i });

    await expect(userTab).toBeVisible();
    await expect(spouseTab).toBeVisible();
    await expect(jointTab).toBeVisible();

    // Test tab navigation
    await spouseTab.click();
    await expect(page.getByText(/Spouse's Aggregated Wealth/i)).toBeVisible();
    
    await jointTab.click();
    await expect(page.getByText(/Total Family Household Wealth/i)).toBeVisible();

    // Test checking an action item
    await userTab.click();
    
    // Look for the first action item. Check if there is an uncompleted action task.
    const actionItemTitle = page.getByText(/הוזלת דמי ניהול בקרן הפנסיה/i);
    await expect(actionItemTitle).toBeVisible();
    
    // Initial state: not completed (no line-through)
    await expect(actionItemTitle).not.toHaveClass(/line-through/);

    // Click the action item itself to cross it off
    const actionItemContainer = actionItemTitle.locator('xpath=./ancestor::div[contains(@class, "rounded-xl p-4")]');
    await actionItemContainer.click();

    // Verify it is crossed off
    await expect(actionItemTitle).toHaveClass(/line-through/);
  });

});
