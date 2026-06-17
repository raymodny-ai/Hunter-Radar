import { useTranslation } from "react-i18next";

export type DisclaimerVariant = "footer" | "banner" | "modal";

export interface DisclaimerProps {
  /** 显示变体:
   * - footer: 用 common.disclaimer(i18n),页脚式分隔线
   * - modal:  用 ultimateAlert.disclaimer(i18n,更强调 FINRA/SEC EDGAR/Yahoo 公开延时)
   * - banner: 黄色高亮 banner,首次进入时高亮警示
   */
  variant?: DisclaimerVariant;
  /** 是否启用竖向滚动(避免 dialog / banner 文字过长时撑破布局) */
  scrollable?: boolean;
  /** 自定义最大高度(px);只在 scrollable=true 时生效 */
  maxHeightPx?: number;
  className?: string;
}

/** 全站统一免责(CR-010 + FE-062 + FE-063)。
 *
 * 硬约束:
 * - 文案侧严禁出现高危推荐词汇(列表见 config.forbidden_recommendation_words,
 *   CR-010 CI 拦截,本组件代码注释中不重复列举)
 * - 必含「仅供参考 / 不构成投资建议」兜底文案
 * - 键盘可达:role="note" / aria-label="disclaimer"
 * - 文本足够长时启用 scrollable,避免 popup 高度失控(FE-063)
 */
export function Disclaimer({
  variant = "footer",
  scrollable = false,
  maxHeightPx,
  className,
}: DisclaimerProps) {
  const { t } = useTranslation();

  const baseCls = "text-slate-400 text-xs leading-relaxed";
  const variantMap: Record<DisclaimerVariant, string> = {
    footer: "border-t border-slate-800 pt-3 mt-3",
    banner:
      "bg-amber-950/30 border border-amber-800/50 rounded px-3 py-2 text-amber-200",
    modal: "border-t border-slate-800 pt-3 mt-3",
  };
  const variantCls = variantMap[variant];
  const scrollCls = scrollable
    ? [
        "overflow-y-auto",
        "pr-2",
        maxHeightPx ? `max-h-[${maxHeightPx}px]` : "max-h-32",
      ].join(" ")
    : "";

  const text =
    variant === "modal"
      ? t("ultimateAlert.disclaimer")
      : t("common.disclaimer");

  return (
    <div
      role="note"
      aria-label="disclaimer"
      data-disclaimer-variant={variant}
      className={[baseCls, variantCls, scrollCls, className]
        .filter(Boolean)
        .join(" ")}
    >
      <span aria-hidden="true">⚠️</span>{" "}
      {text}
    </div>
  );
}
