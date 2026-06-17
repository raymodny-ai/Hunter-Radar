/** FE-082 升级引导 CTA 组件(M6 商业化)。

用途:Pro-only 功能页 / 配额用尽 / 灰度功能不开放等场景,引导用户升级订阅。
变体:
- "inline":行内链接(用于 QuotaBanner / 侧栏)
- "block":居中卡片(用于 Pro-only 功能页正文)
- "modal":遮罩(预留,需配合 useState / onClose)

合规兜底:挂 disclaimer,不做投资建议。
*/
import { useTranslation } from "react-i18next";

export type UpgradeVariant = "inline" | "block" | "modal";

export interface UpgradePromptProps {
  variant?: UpgradeVariant;
  /** 触发原因,展示给用户 */
  reason?: string;
  /** 自定义 className */
  className?: string;
  /** 跳转链接(默认 /subscribe) */
  href?: string;
}

export function UpgradePrompt({
  variant = "inline",
  reason,
  className,
  href = "/subscribe",
}: UpgradePromptProps) {
  const { t } = useTranslation();

  if (variant === "modal") {
    return (
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("marketing.upgradeCta") || "升级 Pro"}
        data-upgrade-prompt="modal"
        className={[
          "fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm",
          "flex items-center justify-center p-6",
          className ?? "",
        ].join(" ")}
      >
        <UpgradePrompt
          variant="block"
          reason={reason}
          href={href}
          className="max-w-md"
        />
      </div>
    );
  }

  if (variant === "block") {
    return (
      <aside
        data-upgrade-prompt="block"
        className={[
          "rounded-lg border border-amber-600/40 bg-amber-950/20",
          "px-5 py-4 flex flex-col items-center gap-3 text-center",
          className ?? "",
        ].join(" ")}
      >
        <span className="text-amber-300 text-xs font-mono uppercase tracking-wider">
          {t("marketing.upgradeTitle") || "解锁完整能力"}
        </span>
        {reason && (
          <p className="text-slate-200 text-sm">{reason}</p>
        )}
        <a
          href={href}
          className="px-4 py-2 rounded-md bg-amber-600 hover:bg-amber-500 text-slate-900 text-sm font-bold transition-colors"
        >
          {t("marketing.upgradeCta") || "升级 Pro"}
        </a>
        <p className="text-xs text-slate-500 leading-relaxed">
          {t("common.disclaimer") ||
            "本产品仅揭示统计异常现象,所有内容仅供研究参考,不构成投资建议。"}
        </p>
      </aside>
    );
  }

  // variant === "inline"
  return (
    <a
      href={href}
      data-upgrade-prompt="inline"
      className={[
        "inline-flex items-center gap-1",
        "text-amber-400 hover:text-amber-300",
        "text-xs underline underline-offset-2",
        className ?? "",
      ].join(" ")}
    >
      <span aria-hidden="true">★</span>
      {t("marketing.upgradeCta") || "升级 Pro"}
    </a>
  );
}

/** 纯函数:给定 tier 返是否需要展示 UpgradePrompt(sandbox 单测用)。 */
export function shouldShowUpgradePrompt(
  tier: "free" | "pro",
  trigger: "exhausted" | "pro-only-feature" | "manual",
): boolean {
  if (tier === "pro") return false;
  return trigger !== "manual";
}