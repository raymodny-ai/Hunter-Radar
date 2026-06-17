/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 信号灯色板(§3.5 共振看板)
        hunter: {
          red:    "#dc2626", // red — 终极警报
          yellow: "#f59e0b", // yellow — 警惕
          gray:   "#94a3b8", // gray — 中性
          green:  "#10b981", // green — 健康
          panic:  "#7c2d12", // 市场 panic 横幅
        },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Cascadia Code"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
