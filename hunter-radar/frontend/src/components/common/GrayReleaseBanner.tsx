/** M6 FE-083 灰度发布提示横幅 — 仅当 gray_release_banner flag 启用时展示。

规则:
- 默认全员可见(rollout_pct=100, default=true)
- 文本可被 i18n featureFlags.bannerText 覆盖
- 提供「了解更多」CTA 链接到 /subscribe 或未来 changelog 页
- 7 天内 dismiss 持久化到 localStorage
*/
import { useTranslation } from "react-i18next";
import { useFeatureFlag, useFeatureFlagSnapshot } from "@/features/useFeatureFlag";

const DISMISS_KEY = "hr_gray_release_dismissed_until";
const DISMISS_DAYS = 7;

function isDismissed(): boolean {
  if (typeof localStorage === "undefined") return false;
  try {
    const until = Number(localStorage.getItem(DISMISS_KEY) || 0);
    return Number.isFinite(until) && until > Date.now();
  } catch {
    return false;
  }
}

function persistDismiss(): void {
  if (typeof localStorage === "undefined") return;
  try {
    const until = Date.now() + DISMISS_DAYS * 24 * 60 * 60 * 1000;
    localStorage.setItem(DISMISS_KEY, String(until));
  } catch {
    // ignore
  }
}

export interface GrayReleaseBannerProps {
  /** 自定义 flag key(默认 gray_release_banner) */
  flagKey?: string;
  /** 强制展示(用于 Storybook / 单测) */
  forceShow?: boolean;
}

export function GrayReleaseBanner({ flagKey = "gray_release_banner", forceShow }: GrayReleaseBannerProps) {
  const { t } = useTranslation();
  const enabled = useFeatureFlag(flagKey, true);
  const snap = useFeatureFlagSnapshot(flagKey);

  if (!forceShow && (!enabled || isDismissed())) return null;

  return (
    <div
      role="region"
      aria-label={t("featureFlags.bannerAriaLabel") || "灰度发布提示"}
      data-gray-release-banner="true"
      data-flag-reason={snap?.reason ?? "unknown"}
      className="border-b border-indigo-800/40 bg-indigo-950/30 text-indigo-100 px-4 py-2 text-sm flex flex-wrap items-center gap-3"
    >
      <span aria-hidden="true" className="text-indigo-300 font-mono">
        [BETA]
      </span>
      <span className="flex-1 min-w-0">
        {t("featureFlags.bannerText") ||
          "你正在体验 Hunter Radar V1.4 商业化版本(灰度中)。如有问题欢迎反馈。"}
      </span>
      <a
        href="/subscribe"
        className="text-xs text-indigo-300 hover:text-indigo-100 underline"
      >
        {t("featureFlags.bannerCta") || "查看升级方案"}
      </a>
      <button
        type="button"
        onClick={persistDismiss}
        aria-label={t("featureFlags.bannerDismiss") || "关闭提示"}
        className="text-indigo-400 hover:text-indigo-200 text-xs underline"
      >
        {t("featureFlags.bannerDismissShort") || "稍后再说"}
      </button>
    </div>
  );
}

/** 纯函数:是否应该展示(单测用)。 */
export function shouldShowGrayReleaseBanner(
  enabled: boolean,
  dismissed: boolean,
): boolean {
  return enabled && !dismissed;
}