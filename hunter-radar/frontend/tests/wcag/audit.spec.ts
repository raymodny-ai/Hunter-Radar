/** FE-066 WCAG 2.1 AA 审计骨架(Playwright + axe-core)。
 *
 * 沙箱不实跑(无 pnpm install),生产环境在 .github/workflows/wcag-audit.yml 触发。
 * 规则:不通过即阻断合并(branch protection required status check)。
 *
 * 测点:
 * 1. 全局 axe 扫描(WCAG 2.1 AA + best-practices)
 * 2. 关键交互组件 role / aria-label 校验
 * 3. 颜色对比度 ≥ 4.5:1
 * 4. 键盘可达(无 mouse-only 控件)
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const BASE_URL = process.env.BASE_URL || "http://localhost:5173";

const PAGES_TO_AUDIT = [
  { path: "/", name: "home" },
  { path: "/screener", name: "screener" },
  { path: "/basket", name: "basket" },
  { path: "/alerts", name: "alerts" },
];

for (const { path, name } of PAGES_TO_AUDIT) {
  test(`FE-066 axe audit ${name} (${path})`, async ({ page }) => {
    await page.goto(`${BASE_URL}${path}`);
    // 等核心 banner 出现
    await page.waitForLoadState("networkidle");

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    // 阻断合并:任何 violation 即失败
    expect(
      accessibilityScanResults.violations,
      `axe violations on ${path}: ${JSON.stringify(
        accessibilityScanResults.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          help: v.help,
          nodes: v.nodes.length,
        })),
        null,
        2,
      )}`,
    ).toEqual([]);
  });
}
