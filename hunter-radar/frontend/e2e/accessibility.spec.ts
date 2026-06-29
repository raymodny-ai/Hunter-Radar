/**
 * FE-157: WCAG AA 自动化审计 — axe-core + Playwright
 *
 * 扫描所有页面无 accessibility violations:
 * - axe-core 0 violations
 * - 关键 aria 属性校验
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const PAGES = [
  { name: "Home", path: "/" },
  { name: "Screener", path: "/screener" },
  { name: "Basket", path: "/basket" },
  { name: "Alerts", path: "/alerts" },
  { name: "Regime", path: "/regime" },
];

for (const { name, path } of PAGES) {
  test(`${name} page has no axe violations`, async ({ page }) => {
    await page.goto(path);

    // Wait for main content to render
    await page.waitForSelector("main", { timeout: 10_000 });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "best-practice"])
      .analyze();

    if (results.violations.length > 0) {
      console.log(`${name} violations:`, JSON.stringify(results.violations, null, 2));
    }
    expect(results.violations).toEqual([]);
  });
}

// Specific a11y checks
test("all chart containers have aria-label", async ({ page }) => {
  await page.goto("/");

  // Navigate to a symbol detail page if search works
  const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/搜索/));
  if (await searchInput.isVisible()) {
    await searchInput.fill("AAPL");
    await searchInput.press("Enter");
    await page.waitForURL(/\/symbol\//);

    // Check chart containers have aria-label
    const charts = page.locator('[role="img"]');
    const count = await charts.count();
    for (let i = 0; i < count; i++) {
      const label = await charts.nth(i).getAttribute("aria-label");
      expect(label).toBeTruthy();
    }
  }
});
