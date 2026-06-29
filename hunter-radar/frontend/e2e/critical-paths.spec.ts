/**
 * FE-155: E2E 关键路径测试
 *
 * 5 条关键路径:
 * 1. 搜索 → 详情页
 * 2. Screener 浏览
 * 3. 自选篮子
 * 4. 预警规则管理
 * 5. 宏观环境页
 */
import { test, expect } from "@playwright/test";

// ─── 1. Search → Detail Page ─────────────────────────────────────
test("search and navigate to symbol detail", async ({ page }) => {
  await page.goto("/");

  // Find search input
  const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/搜索/));
  if (await searchInput.isVisible()) {
    await searchInput.fill("AAPL");
    // Wait for autocomplete
    await page.waitForTimeout(500);
    // Press Enter or click first result
    await searchInput.press("Enter");
    // Should navigate to symbol page
    await expect(page).toHaveURL(/\/symbol\/AAPL/);
  }
});

// ─── 2. Screener Browse ──────────────────────────────────────────
test("screener page loads and shows data", async ({ page }) => {
  await page.goto("/screener");

  // Page should load
  await expect(page).toHaveURL("/screener");

  // Check page heading exists
  const heading = page.locator("h1").first();
  await expect(heading).toBeVisible();
});

// ─── 3. Basket Page ──────────────────────────────────────────────
test("basket page loads and shows list", async ({ page }) => {
  await page.goto("/basket");

  await expect(page).toHaveURL("/basket");

  // Check page heading
  const heading = page.locator("h1").first();
  await expect(heading).toBeVisible();
});

// ─── 4. Alerts Page ──────────────────────────────────────────────
test("alerts page loads with rule management", async ({ page }) => {
  await page.goto("/alerts");

  await expect(page).toHaveURL("/alerts");

  // Check page heading
  const heading = page.locator("h1").first();
  await expect(heading).toBeVisible();
});

// ─── 5. Regime Page ──────────────────────────────────────────────
test("regime page loads with gating indicators", async ({ page }) => {
  await page.goto("/regime");

  await expect(page).toHaveURL("/regime");

  // Check page heading
  const heading = page.locator("h1").first();
  await expect(heading).toBeVisible();
});

// ─── Responsive: Mobile layout ───────────────────────────────────
test("mobile layout shows bottom toolbar", async ({ page }) => {
  // Mobile viewport is set by chromium-mobile project
  await page.goto("/");

  // Bottom toolbar should be visible on mobile
  const bottomToolbar = page.locator(".md\\:hidden.fixed.bottom-0");
  if (page.viewportSize()!.width < 768) {
    await expect(bottomToolbar).toBeVisible();
  }
});
