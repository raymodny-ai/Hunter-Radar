/** BD-105/FE-082 Pro 徽章组件(M6 商业化)。

用途:挂在 Pro-only 功能 / 区域旁,提示用户该功能需 Pro 订阅。
色系:琥珀/金,与 QuotaBanner palette 区分。

沙箱降级:无 i18n key 时回退到「PRO」英文。
*/
import { useTranslation } from "react-i18next";

export interface ProBadgeProps {
  /** "compact"=8px 方块图标;"full"=带文字「Pro only」 */
  variant?: "compact" | "full";
  /** 自定义 className */
  className?: string;
  /** 强制显示英文(国际化未配置时) */
  forceEn?: boolean;
}

export function ProBadge({ variant = "full", className, forceEn }: ProBadgeProps) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language || "zh-CN";
  const useEn = forceEn || lang.startsWith("en");

  if (variant === "compact") {
    return (
      <span
        data-pro-badge="compact"
        aria-label={useEn ? "Pro only" : "仅 Pro"}
        title={useEn ? "Pro subscription required" : "需 Pro 订阅"}
        className={[
          "inline-flex items-center justify-center",
          "px-1.5 py-0.5 rounded text-[10px] font-mono font-bold",
          "bg-amber-500/20 text-amber-300 border border-amber-500/40",
          "leading-none",
          className ?? "",
        ].join(" ")}
      >
        PRO
      </span>
    );
  }

  const text = t("marketing.proBadge") || (useEn ? "Pro only" : "Pro 专享");
  return (
    <span
      data-pro-badge="full"
      className={[
        "inline-flex items-center gap-1 px-2 py-0.5 rounded",
        "bg-amber-500/20 text-amber-300 border border-amber-500/40",
        "text-xs font-semibold tracking-wide",
        className ?? "",
      ].join(" ")}
    >
      <span aria-hidden="true">★</span>
      {text}
    </span>
  );
}

/** 纯函数:给定 tier 返是否需要展示 ProBadge(sandbox 单测用)。 */
export function shouldShowProBadge(tier: "free" | "pro"): boolean {
  return tier !== "pro";
}