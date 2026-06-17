import { createRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { ProBadge } from "@/components/common/ProBadge";
import { UpgradePrompt } from "@/components/common/UpgradePrompt";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/alerts",
  component: AlertsPage,
});

function AlertsPage() {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{t("routes.alerts")}</h1>
        <ProBadge />
      </header>
      <UpgradePrompt
        variant="block"
        reason={
          t("marketing.alertsReason") ||
          "预警规则引擎与多通道推送(邮件 / Web Push)仅对 Pro 订阅开放。"
        }
      />
      <div className="text-slate-400 text-sm">
        BD-073 规则引擎 + BD-074 推送通道待 M4 对接。当前为占位页。
      </div>
    </div>
  );
}