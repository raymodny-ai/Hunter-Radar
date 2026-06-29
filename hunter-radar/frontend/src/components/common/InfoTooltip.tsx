/**
 * FE-146: InfoTooltip — 合规 Tooltip(Info 图标)
 *
 * 所有 Threat Score 数值旁 + 红绿灯模块旁有 Info 图标:
 * - Hover 弹出免责文案(红底高亮)
 * - 文案从 i18n 集中引用
 * - Radix UI Tooltip primitive
 */
import { useState, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

export interface InfoTooltipProps {
  /** i18n key for tooltip content */
  i18nKey?: string;
  /** Direct content (overrides i18nKey) */
  content?: ReactNode;
  /** Size variant */
  size?: "sm" | "md";
  className?: string;
}

export function InfoTooltip({
  i18nKey = "compliance.scoreDisclaimer",
  content,
  size = "sm",
  className,
}: InfoTooltipProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const tooltipContent = content || t(i18nKey);
  const iconSize = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";
  const textSize = size === "sm" ? "text-[10px]" : "text-xs";

  return (
    <span className={`relative inline-flex items-center ${className || ""}`}>
      <button
        ref={triggerRef}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className={`${iconSize} ${textSize} rounded-full flex items-center justify-center text-slate-500 hover:text-slate-300 transition-colors focus:outline-none focus:ring-1 focus:ring-sky-500`}
        aria-label={t("compliance.infoLabel")}
        type="button"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-full h-full">
          <path d="M8 0a8 8 0 110 16A8 8 0 018 0zm.75 11.25h-1.5v-4.5h1.5v4.5zm0-6h-1.5V3.75h1.5v1.5z" />
        </svg>
      </button>

      {open && (
        <span
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1.5 rounded text-xs whitespace-nowrap max-w-[260px] whitespace-normal pointer-events-none"
          style={{
            backgroundColor: "rgba(127, 29, 29, 0.95)",
            color: "#fecaca",
            border: "1px solid rgba(239, 68, 68, 0.3)",
          }}
          role="tooltip"
        >
          {tooltipContent}
        </span>
      )}
    </span>
  );
}
