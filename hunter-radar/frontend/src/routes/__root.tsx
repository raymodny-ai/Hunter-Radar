import { Link, Outlet, createRootRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { DataStatusBanner } from "@/components/common/DataStatusBanner";
import { LogPanel } from "@/components/common/LogPanel";
import { Disclaimer } from "@/components/common/Disclaimer";
import { GrayReleaseBanner } from "@/components/common/GrayReleaseBanner";
import { PWAInstallBanner } from "@/components/common/PWAInstallBanner";
import { QuotaBanner } from "@/components/common/QuotaBanner";
import { RegimeBanner } from "@/components/radar/RegimeBanner";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const { t } = useTranslation();
  const [logVisible, setLogVisible] = useState(false);

  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-slate-800 px-4 py-3 flex items-center gap-6">
        <Link to="/" className="font-bold text-lg tracking-wider">
          🎯 {t("app.name")}
        </Link>
        <nav className="flex gap-4 text-sm text-slate-300">
          <Link to="/screener" className="hover:text-white" activeProps={{ className: "text-white" }}>
            {t("routes.screener")}
          </Link>
          <Link to="/basket" className="hover:text-white" activeProps={{ className: "text-white" }}>
            {t("routes.basket")}
          </Link>
          <Link to="/alerts" className="hover:text-white" activeProps={{ className: "text-white" }}>
            {t("routes.alerts")}
          </Link>
          {/* subscribe page removed (payment features removed) */}
        </nav>
        <div className="flex-1" />
        <button
          onClick={() => setLogVisible(!logVisible)}
          className={`text-xs px-2 py-1 rounded font-mono border ${
            logVisible
              ? "bg-sky-900/50 border-sky-700 text-sky-200"
              : "bg-slate-800/50 border-slate-700 text-slate-400 hover:text-slate-200"
          }`}
          title={logVisible ? "关闭日志面板" : "打开日志面板"}
        >
          📋 Logs
        </button>
      </header>

      <RegimeBanner />
      {/* m5t6 FE-061 全局数据未到位门控 */}
      <DataStatusBanner />
      {/* m5t8 FE-064 BD-076 免费版每日查询配额提示(pro 不展示) */}
      <QuotaBanner />
      {/* m6t3 BD-101 PWA 安装提示(Chrome/Edge/Android 自动弹,iOS Safari 手动引导) */}
      <PWAInstallBanner />
      {/* m6t7 FE-083 灰度发布提示横幅(gray_release_banner flag 控制) */}
      <GrayReleaseBanner />

      <main className="flex-1 px-4 py-6 max-w-screen-2xl w-full mx-auto">
        <Outlet />
      </main>

      {/* 后台日志面板 */}
      <LogPanel visible={logVisible} />

      <footer className="border-t border-slate-800 px-4 py-3 text-xs text-slate-500">
        <Disclaimer />
      </footer>
    </div>
  );
}
