import { test, expect } from "@playwright/test";

test("smoke test in DEMO_MODE: search -> score visible -> hotels listed -> narrative badge appears", async ({
  page,
}) => {
  // 1. Navigate to main dashboard with initial search query
  await page.goto("/?q=Manali&alpha=0.7");

  // 2. Verify status banner is visible
  const banner = page.locator("text=/LIVE DATA ACTIVE|DEMO MODE ACTIVE/");
  await expect(banner).toBeVisible();

  // 3. Verify safety score is visible and within 0-100 bounds
  const scoreEl = page.locator("#overall-safety-score");
  await expect(scoreEl).toBeVisible({ timeout: 10000 });
  const scoreText = await scoreEl.textContent();
  const scoreNum = parseInt(scoreText || "0", 10);
  expect(scoreNum).toBeGreaterThanOrEqual(0);
  expect(scoreNum).toBeLessThanOrEqual(100);

  // 4. Verify explicit band label text is visible
  const bandLabel = page.locator("#safety-band-label");
  await expect(bandLabel).toBeVisible();

  // 5. Verify hotels are listed and ranked
  const hotelCards = page.locator('[id^="hotel-card-"]');
  await expect(hotelCards.first()).toBeVisible({ timeout: 10000 });
  const hotelCount = await hotelCards.count();
  expect(hotelCount).toBeGreaterThan(0);

  // 6. Verify AI narrative card and verification badge appear
  const narrativeBadge = page.locator("#narrative-verification-badge");
  await expect(narrativeBadge).toBeVisible({ timeout: 15000 });
});
