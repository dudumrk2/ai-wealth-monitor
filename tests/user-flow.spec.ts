import { test, expect } from '@playwright/test';

test.describe('AI Wealth Monitor - Flow Tests (Phase 3)', () => {

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.removeItem('wealth_monitor_onboarding_done');
      localStorage.removeItem('wealth_monitor_family_config');
    });
  });

  test('מסך ברוכים - Welcome: should show two CTA paths', async ({ page }) => {
    await page.goto('/login');
    // The CTA headings and buttons should both be visible
    await expect(page.getByRole('heading', { name: /יצירת משפחה חדשה/i })).toBeVisible();
    await expect(page.getByText(/כניסה לחשבון משפחה קיים/i)).toBeVisible();
    await expect(page.getByText(/הצפנה ברמה בנקאית/i)).toBeVisible();
  });

  test('הכוונה - Onboarding: name fields for both members are visible', async ({ page }) => {
    await page.goto('/onboarding?demo=true');
    await expect(page.getByRole('heading', { name: /הגדרת המשפחה/i })).toBeVisible();
    // Check name input fields
    await expect(page.getByPlaceholder(/דוד/i)).toBeVisible();
    await expect(page.getByPlaceholder(/מירי/i)).toBeVisible();
  });

  test('הכוונה - Onboarding: saves names and redirects to dashboard', async ({ page }) => {
    await page.goto('/onboarding?demo=true');

    await page.getByPlaceholder(/דוד/i).fill('אבי');
    await page.getByPlaceholder(/מירי/i).fill('שרה');

    // Button should be enabled now
    const submitBtn = page.getByRole('button', { name: /סיום הגדרה/i });
    await expect(submitBtn).not.toBeDisabled();
    await submitBtn.click();

    await expect(page).toHaveURL(/\/dashboard/);

    // Names should appear as tab labels
    await expect(page.getByRole('button', { name: 'אבי' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'שרה' })).toBeVisible();
  });

  test('לוח בקרה - Dashboard: default tab is Joint View (תצוגה משותפת)', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('wealth_monitor_onboarding_done', 'true');
      localStorage.setItem('wealth_monitor_family_config', JSON.stringify({
        householdName: 'משפחת ישראלי',
        member1: { name: 'יוסי', email: 'yossi@gmail.com' },
        member2: { name: 'רחל', email: 'rachel@gmail.com' },
      }));
    });
    await page.goto('/dashboard?demo=true');

    // Joint view wealth card should be visible by default
    await expect(page.getByText(/עושר משפחתי מאוחד/i)).toBeVisible();
    await expect(page.getByText(/פיזור נכסים/i)).toBeVisible();

    // Tabs should use the names from config
    await expect(page.getByRole('button', { name: 'יוסי' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'רחל' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'תצוגה משותפת' })).toBeVisible();

    // Member name badges in the joint wealth card specifically
    const wealthCard = page.locator('p:has-text("עושר משפחתי מאוחד")').locator('..');
    await expect(wealthCard.getByText('יוסי')).toBeVisible();
    await expect(wealthCard.getByText('רחל')).toBeVisible();
  });

  test('פעולות נדרשות - Action Items: clicking should cross off item', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('wealth_monitor_onboarding_done', 'true');
    });
    await page.goto('/dashboard?demo=true');

    const card = page.locator('[id="action-item-task_2"]');
    await expect(card).toBeVisible();
    const title = card.locator('h3');
    await expect(title).not.toHaveClass(/line-through/);
    await card.click();
    await expect(title).toHaveClass(/line-through/);
  });

  test('הגדרות - Settings: can add authorized email and delete modal requires confirmation', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('wealth_monitor_onboarding_done', 'true');
      localStorage.setItem('wealth_monitor_family_config', JSON.stringify({
        familyId: 'local-demo',
        householdName: 'משפחת ישראלי',
        member1: { name: 'יוסי', email: 'yossi@gmail.com' },
        member2: { name: 'רחל', email: 'rachel@gmail.com' },
        extraAuthorizedEmails: []
      }));
    });
    await page.goto('/settings?demo=true');

    // Add email
    const emailInput = page.getByPlaceholder(/הכנס כתובת Google/i);
    await emailInput.fill('kid@gmail.com');
    await page.getByRole('button', { name: 'הוסף' }).click();
    await expect(page.getByText('kid@gmail.com')).toBeVisible();

    // Delete modal validation
    await page.getByRole('button', { name: /מחק משפחה/i }).click();
    const modal = page.locator('.fixed.inset-0 .bg-white').first();
    await expect(modal.getByText('מחיקת המשפחה')).toBeVisible();
    
    const confirmBtn = modal.getByRole('button', { name: /מחק לצמיתות/i });
    await expect(confirmBtn).toBeDisabled();
    
    // Type incorrect name
    await modal.getByRole('textbox').fill('לא נכון');
    await expect(confirmBtn).toBeDisabled();
    
    // Type correct name
    await modal.getByRole('textbox').fill('משפחת ישראלי');
    await expect(confirmBtn).not.toBeDisabled();
  });

  test('השקעות אלטרנטיביות - Dashboard: can add new alternative asset', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('wealth_monitor_onboarding_done', 'true');
      localStorage.setItem('wealth_monitor_family_config', JSON.stringify({
        householdName: 'משפחת ישראלי',
        member1: { name: 'יוסי', email: 'yossi@gmail.com' },
        member2: { name: 'רחל', email: 'rachel@gmail.com' },
      }));
    });
    // The user has mock data loaded automatically in the component
    await page.goto('/dashboard?demo=true');

    // Click "Add Asset" button on Alternative Investments table
    const addBtn = page.locator('button').filter({ hasText: 'הוסף נכס' }).first();
    await addBtn.scrollIntoViewIfNeeded();
    await addBtn.click();

    const modal = page.locator('.fixed.inset-0 .bg-white').first();
    await expect(modal.getByText('הוספת נכס חדש')).toBeVisible();

    await modal.getByPlaceholder(/דירה להשכרה/i).fill('רכב להשכרה');
    await modal.locator('input[type="number"]').first().fill('150000'); // balance
    
    const saveBtn = modal.getByRole('button', { name: 'הוסף נכס' });
    await expect(saveBtn).not.toBeDisabled();
    await saveBtn.click();

    // Verify it was added to the table
    await expect(page.getByText('רכב להשכרה')).toBeVisible();
  });

});
