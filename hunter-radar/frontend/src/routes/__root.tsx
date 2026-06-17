import { Link, Outlet, createRootRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { DataStatusBanner } from "@/components/common/DataStatusBanner";
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
          {/* m6t5 FE-081 BD-105 订阅页 */}
          <Link to="/subscribe" className="hover:text-white" activeProps={{ className: "text-white" }}>
            {t("routes.subscribe")}
          </Link>
        </nav>
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

      <footer className="border-t border-slate-800 px-4 py-3 text-xs text-slate-500">
        <Disclaimer />
      </footer>
    </div>
  );
}
