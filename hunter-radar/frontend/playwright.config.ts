/**
 * FE-155: Playwright E2E 配置 — 关键路径测试
 *
 * 5 条关键路径:
 * 1. 搜索 → 详情页
 * 2. Screener 浏览
 * 3. 自选篮子 CRUD
 * 4. 预警规则管理
 * 5. 宏观环境页
 *
 * 响应式三档:xl / md / mobile
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  retries: 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    // Desktop xl (>1280px)
    {
      name: "chromium-xl",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    // Tablet md (768-1280px)
    {
      name: "chromium-md",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 768 } },
    },
    // Mobile (<768px)
    {
      name: "chromium-mobile",
      use: { ...devices["Pixel 5"] },
    },
  ],
  webServer: {
    command: "npx vite --port 5173",
    port: 5173,
    reuseExistingServer: true,
  },
});
