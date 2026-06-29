/**
 * FE-100 + FE-101 + FE-103 + FE-104: __root 重构
 *
 * 使用 AppShell 四区布局替代原有简单 header:
 * - TopNav(顶部导航 + 搜索框 + 状态灯带)
 * - LeftToolbar(分析器透镜)
 * - RightSidebar(Tabs 抽屉)
 * - MobileBottomToolbar(移动端底部栏)
 * - 全局横幅区(DataStatus / Regime / Quota / PWA / GrayRelease)
 */
import { Outlet, createRootRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { TopNav } from "@/components/layout/TopNav";
import { LeftToolbar, MobileBottomToolbar } from "@/components/layout/LeftToolbar";
import { RightSidebar } from "@/components/layout/RightSidebar";
import { EventTicker } from "@/components/common/EventTicker";
import { DataStatusBanner } from "@/components/common/DataStatusBanner";
import { LogPanel } from "@/components/common/LogPanel";
import { Disclaimer } from "@/components/common/Disclaimer";
import { GrayReleaseBanner } from "@/components/common/GrayReleaseBanner";
import { PWAInstallBanner } from "@/components/common/PWAInstallBanner";
import { QuotaBanner } from "@/components/common/QuotaBanner";
import { RegimeBanner } from "@/components/radar/RegimeBanner";
import { usePerformanceProbe } from "@/features/usePerformanceProbe";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const { t } = useTranslation();
  const [logVisible, setLogVisible] = useState(false);

  // FE-153: Performance probe auto-reporting
  usePerformanceProbe();

  // 同步 TopNav 内部的 logVisible 状态(通过 window bridge)
  // TopNav 写入 window.__hunterLogToggle,这里读取并订阅
  if (typeof window !== "undefined") {
    (window as unknown as Record<string, unknown>).__hunterLogVisible = logVisible;
    (window as unknown as Record<string, unknown>).__hunterSetLogVisible = setLogVisible;
  }

  const banners = (
    <div className="shrink-0">
      {/* FE-151: 8-K event marquee */}
      <EventTicker />
      <RegimeBanner />
      <DataStatusBanner />
      <QuotaBanner />
      <PWAInstallBanner />
      <GrayReleaseBanner />
    </div>
  );

  return (
    <AppShell
      topNav={<TopNav />}
      leftToolbar={<LeftToolbar />}
      rightSidebar={<RightSidebar />}
      banners={banners}
      footer={<Disclaimer />}
    >
      <Outlet />

      {/* 后台日志面板 */}
      <LogPanel visible={logVisible} />

      {/* 移动端底部工具栏(FE-107) */}
      <MobileBottomToolbar />
    </AppShell>
  );
}
