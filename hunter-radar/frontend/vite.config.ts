import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { TanStackRouterVite } from "@tanstack/router-vite-plugin";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  plugins: [
    react(),
    TanStackRouterVite(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      // 离线跳转: SPA 深链接(/screener /basket 等)断网时落 offline.html
      // ponytail: navigateFallback removed — VitePWA 1.0+ doesn't support this in type defs

      manifest: {
        name: "Hunter Radar V1.4",
        short_name: "Hunter",
        description: "美股盘后另类数据雷达",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/",
        scope: "/",
        lang: "zh-CN",
        // PWA 可装提示必现 192/512 两图(m6t3 详化)
        icons: [
          { src: "/icon-192.svg", sizes: "192x192", type: "image/svg+xml" },
          { src: "/icon-512.svg", sizes: "512x512", type: "image/svg+xml", purpose: "any" },
          { src: "/icon-512.svg", sizes: "512x512", type: "image/svg+xml", purpose: "maskable" },
        ],
      },
      workbox: {
        // 预缓存 offline.html,断网跳转不失败
        runtimeCaching: [
          // 1. /api/v1/symbols/.*/threat — 报告接口 12h TTL(对应后端 cache_ttl_report_seconds)
          {
            urlPattern: /\/api\/v1\/symbols\/.*\/threat/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "hunter-threat",
              expiration: { maxAgeSeconds: 60 * 60 * 12 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // 2. /api/v1/regime /data-status /auth/quota — 轻量端点 5min TTL
          {
            urlPattern: /\/api\/v1\/(regime|data-status|auth\/quota)/,
            handler: "NetworkFirst",
            options: {
              cacheName: "hunter-meta",
              networkTimeoutSeconds: 4,
              expiration: { maxAgeSeconds: 60 * 5 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // 3. /api/v1/screener /baskets /alert-rules /alerts — 用户数据 NetworkFirst 30s
          {
            urlPattern: /\/api\/v1\/(screener|baskets|alert-rules|alerts)/,
            handler: "NetworkFirst",
            options: {
              cacheName: "hunter-user",
              networkTimeoutSeconds: 4,
              expiration: { maxAgeSeconds: 60 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // 4. 静态资源 .js .css 走 CacheFirst
          {
            urlPattern: /\.(?:js|css|woff2?)$/,
            handler: "CacheFirst",
            options: {
              cacheName: "hunter-static",
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // 5. 图片走 StaleWhileRevalidate
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|webp|gif|ico)$/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "hunter-img",
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 7 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      devOptions: {
        enabled: false, // dev 模式不开 SW,避免热重载被缓存
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts"],
          charts: ["lightweight-charts"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
