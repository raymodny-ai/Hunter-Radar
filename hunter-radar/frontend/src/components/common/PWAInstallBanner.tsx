/** BD-101 PWA 安装提示 banner(全局可挂载,优雅降级)。
 *
 * 规则:
 * - standalone(已安装)不展示
 * - 7 天内 dismissed 不展示
 * - Chrome/Edge/Android:`installPrompt` 就绪时展示 + 「安装到桌面」按钮
 * - iOS Safari:无 installPrompt 但 isIOS 时,展示「分享 → 添加到主屏」引导
 * - 其他:不展示
 *
 * 沙箱降级:
 * - `installPrompt` 为 null 且非 iOS:不展示
 * - `installPrompt.prompt()` 失败:catch 后静默返 outcome
 *
 * 兜底:不做投资建议(挂 disclaimer)
 */
import { useTranslation } from "react-i18next";

import { usePWAInstall } from "@/features/usePWAInstall";

export interface PWAInstallBannerProps {
  /** 强制展示(用于 Storybook / 单测) */
  forceShow?: boolean;
  /** 模拟 iOS 设备 */
  forceIOS?: boolean;
}

export function PWAInstallBanner({ forceShow, forceIOS }: PWAInstallBannerProps) {
  const { t } = useTranslation();
  const pwa = usePWAInstall();
  const isIOS = forceIOS ?? pwa.isIOS;

  if (!forceShow) {
    if (pwa.isStandalone) return null;
    if (pwa.isDismissed) return null;
    if (!pwa.installPrompt && !isIOS) return null;
  }

  const handleInstall = async () => {
    const outcome = await pwa.install();
    if (outcome === "accepted") {
      // 安装成功,自动 dismiss
      pwa.dismiss();
    }
  };

  return (
    <div
      role="region"
      aria-label={t("pwa.install.ariaLabel") || "PWA 安装提示"}
      data-pwa-prompt="true"
      className="border-b border-sky-800/40 bg-sky-950/30 text-sky-100 px-4 py-2 text-sm flex flex-wrap items-center gap-3"
    >
      <span aria-hidden="true" className="text-sky-300 font-mono">
        [PWA]
      </span>
      <span className="flex-1 min-w-0">
        {isIOS
          ? t("pwa.install.iosHint") ||
            "iOS 用户:在 Safari 點擊分享按鈕 → 「添加到主屏幕」,即可離線使用。"
          : t("pwa.install.hint") ||
            "將 Hunter Radar 安裝到桌面,離線也能查看最新報告與預警。"}
      </span>
      {isIOS ? (
        <span className="text-xs text-sky-400 font-mono">[Safari 分享]</span>
      ) : (
        <button
          type="button"
          onClick={handleInstall}
          className="px-3 py-1 rounded bg-sky-700 hover:bg-sky-600 text-white text-xs font-medium transition-colors"
        >
          {t("pwa.install.cta") || "安裝到桌面"}
        </button>
      )}
      <button
        type="button"
        onClick={pwa.dismiss}
        aria-label={t("pwa.install.dismiss") || "關閉安裝提示"}
        className="text-sky-400 hover:text-sky-200 text-xs underline"
      >
        {t("pwa.install.dismissShort") || "稍後再說"}
      </button>
    </div>
  );
}

/** 純函數:給定 hook 結果,返 banner 是否應該展示(sandbox 自測用)。 */
export function shouldShowPWAInstall(
  pwa: Pick<ReturnType<typeof usePWAInstall>, "isStandalone" | "isDismissed" | "installPrompt" | "isIOS">,
): boolean {
  if (pwa.isStandalone) return false;
  if (pwa.isDismissed) return false;
  if (!pwa.installPrompt && !pwa.isIOS) return false;
  return true;
}
