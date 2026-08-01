/**
 * PRD §7.3: Offline banner
 *
 * 网络断开时在页面顶部显示离线横幅（cached shell 仍可浏览）。
 * Mutation 队列：TanStack Query v5 的 onlineManager 默认在离线时暂停
 * queries/mutations，恢复网络后自动重放（无需手动队列）。
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

export function OfflineBanner() {
  const { t } = useTranslation();
  const [offline, setOffline] = useState(
    () => typeof navigator !== "undefined" && !navigator.onLine,
  );

  useEffect(() => {
    const onOffline = () => setOffline(true);
    const onOnline = () => setOffline(false);
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-2 bg-amber-900/60 border-b border-amber-700/50 px-4 py-1.5 text-xs text-amber-200"
    >
      <span aria-hidden="true">📡</span>
      <span>{t("pwa.offline.banner")}</span>
    </div>
  );
}
