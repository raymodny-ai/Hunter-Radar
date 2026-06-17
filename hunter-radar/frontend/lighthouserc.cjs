/** FE-068 Lighthouse CI 配置(锁定 v1.4.1 性能基线)。 */
module.exports = {
  ci: {
    collect: {
      startServerCommand: "pnpm dev --port 5173",
      startServerReadyPattern: "ready in",
      startServerReadyTimeout: 60000,
      url: [
        "http://localhost:5173/",
        "http://localhost:5173/screener",
        "http://localhost:5173/basket",
        "http://localhost:5173/alerts",
      ],
      numberOfRuns: 3,
      settings: {
        chromeFlags: "--no-sandbox --headless=new",
        preset: "desktop",
      },
    },
    assert: {
      // 硬约束:低于以下阈值即阻断合并
      assertions: {
        "categories:performance": ["error", { minScore: 0.85 }],
        "categories:accessibility": ["error", { minScore: 0.95 }],
        "categories:best-practices": ["error", { minScore: 0.90 }],
        "categories:seo": ["warn", { minScore: 0.80 }],
        // 核心 Web 指标
        "first-contentful-paint": ["warn", { maxNumericValue: 1800 }],
        "largest-contentful-paint": ["error", { maxNumericValue: 2500 }],
        "cumulative-layout-shift": ["error", { maxNumericValue: 0.1 }],
        "total-blocking-time": ["warn", { maxNumericValue: 200 }],
      },
    },
    upload: {
      target: "filesystem",
      outputDir: "./.lighthouseci",
    },
  },
};
