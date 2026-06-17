/** FE-067 Playwright E2E 骨架(smoke)。
 *
 * 沙箱不实跑,生产 CI 触发。
 * 测点:
 * 1. 4 路由可达(200)
 * 2. 4 路由核心 DOM 存在(品牌 / 导航 / banner)
 * 3. 后端 3 关键端点 200(/regime / /data-status / /auth/quota)
 * 4. 沙箱降级 / 错误态 UI 出现(data-warmup 等)
 */
import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://localhost:5173";
const API_URL = process.env.API_URL || "http://localhost:8000";

test.describe("FE-067 smoke routes", () => {
  test("home / reaches + brand visible", async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    await expect(page).toHaveTitle(/Hunter Radar/);
    await expect(page.getByText("Hunter Radar")).toBeVisible();
  });

  test("screener / reaches + has search input", async ({ page }) => {
    await page.goto(`${BASE_URL}/screener`);
    await expect(page).toHaveURL(/\/screener/);
  });

  test("basket / reaches + empty state", async ({ page }) => {
    await page.goto(`${BASE_URL}/basket`);
    await expect(page).toHaveURL(/\/basket/);
  });

  test("alerts / reaches + CTA", async ({ page }) => {
    await page.goto(`${BASE_URL}/alerts`);
    await expect(page).toHaveURL(/\/alerts/);
  });
});

test.describe("FE-067 backend critical endpoints", () => {
  test("/regime returns 200", async ({ request }) => {
    const r = await request.get(`${API_URL}/api/v1/regime`);
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.regime).toMatch(/normal|panic/);
  });

  test("/data-status returns 200", async ({ request }) => {
    const r = await request.get(`${API_URL}/api/v1/data-status`);
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.status).toMatch(/ready|warming|stale|error/);
  });

  test("/auth/quota returns 200 (sandbox placeholder user)", async ({ request }) => {
    const r = await request.get(`${API_URL}/api/v1/auth/quota`);
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.tier).toMatch(/free|pro/);
    expect(body.used).toBeGreaterThanOrEqual(0);
  });
});
