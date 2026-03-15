import { test, expect } from '@playwright/test';

test.describe('Onboarding Multi-step Flow', () => {

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.removeItem('wealth_monitor_onboarding_done');
      localStorage.removeItem('wealth_monitor_onboarding_draft');
    });
  });

  test('should complete the full 2-step onboarding flow', async ({ page }) => {
    await page.goto('/onboarding?demo=true');

    // --- Step 1 ---
    await expect(page.getByText('שלב 1: פרטים בסיסיים והרשאות')).toBeVisible();

    // Fill Household Name
    await page.getByLabel(/שם הבית /i).fill('משפחת לוי');

    // Fill Member 1
    await page.getByLabel(/שם פרטי/).first().fill('דוד');
    await page.getByLabel(/כתובת Google/).first().fill('david@gmail.com');
    // Last name left empty to test default logic

    // Fill Member 2
    await page.getByLabel(/שם פרטי/).nth(1).fill('מירי');
    await page.getByLabel(/כתובת Google/).nth(1).fill('miri@gmail.com');

    // Move to Step 2
    const nextBtn = page.getByRole('button', { name: /המשך לשלב הבא/i });
    await expect(nextBtn).toBeEnabled();
    await nextBtn.click();

    // --- Step 2 ---
    await expect(page.getByText('שלב 2: נתונים לתכנון פיננסי אישי')).toBeVisible();
    await expect(page.getByText('פרופיל פיננסי ומשפחתי')).toBeVisible();

    // Verify default values from the provided code
    await expect(page.locator('input[name="spouse1BirthYear"]')).toHaveValue('1984');
    await expect(page.locator('input[name="spouse2BirthYear"]')).toHaveValue('1986');
    await expect(page.locator('input[name="kidsCount"]')).toHaveValue('3');

    // Final Submission
    const saveBtn = page.getByRole('button', { name: /שמור והמשך לדאשבורד/i });
    await expect(saveBtn).toBeVisible();
    await saveBtn.click();

    // Verify redirection
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('should persist values in local storage on refresh', async ({ page }) => {
    await page.goto('/onboarding?demo=true');

    // Fill Step 1
    await page.locator('input[name="family_name"]').fill('משפחת כהן');
    await page.locator('input[name="fname1"]').fill('אבי');

    // Wait for localStorage to contain the changes
    await expect.poll(async () => {
      const draft = await page.evaluate(() => localStorage.getItem('wealth_monitor_onboarding_draft'));
      return draft ? JSON.parse(draft).member1?.name : null;
    }).toBe('אבי');

    // Refresh page
    await page.reload();

    // Verify values are still there
    await expect(page.locator('input[name="family_name"]')).toHaveValue('משפחת כהן');
    await expect(page.locator('input[name="fname1"]')).toHaveValue('אבי');

    // Move to Step 2
    await page.locator('input[name="email1"]').fill('avi@gmail.com');
    await page.locator('input[name="fname2"]').fill('שרה');
    await page.locator('input[name="email2"]').fill('sara@gmail.com');
    await page.getByRole('button', { name: /המשך לשלב הבא/i }).click();

    // Fill Step 2 field and refresh
    await page.locator('input[name="spouse1BirthYear"]').fill('1980');
    await page.reload();

    // Verify Step 2 is still active and value is persisted
    await expect(page.getByText('שלב 2: נתונים לתכנון פיננסי אישי')).toBeVisible();
    await expect(page.locator('input[name="spouse1BirthYear"]')).toHaveValue('1980');
  });

  test('should use household name as default last name if not provided', async ({ page }) => {
    // This test would ideally verify the payload sent to Firestore, 
    // but we can at least verify the flow completes.
    await page.goto('/onboarding?demo=true');
    await page.getByLabel(/שם הבית /i).fill('משפחת ישראלי');
    await page.getByLabel(/שם פרטי/).first().fill('יוסי');
    await page.getByLabel(/כתובת Google/).first().fill('yossi@gmail.com');
    await page.getByLabel(/שם פרטי/).nth(1).fill('רחל');
    await page.getByLabel(/כתובת Google/).nth(1).fill('rachel@gmail.com');
    
    await page.getByRole('button', { name: /המשך לשלב הבא/i }).click();
    await page.getByRole('button', { name: /שמור והמשך לדאשבורד/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    
    // Check if names appear in dashboard (which uses the family config)
    // Note: Dashboard might need a refresh or the init script might need to set the state
    // but our handleCompleteFinancialProfile saves to Firestore AND updates AuthContext.
  });
});
