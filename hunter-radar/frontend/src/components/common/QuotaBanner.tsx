/** §6.3 FE-064 全局 quota banner。
 *
 * 规则:
 * - pro tier(remaining=-1)不展示
 * - free tier,remaining <= 0:红色 + 「今日配额已用完,请明日再来或升级 Pro」
 * - free tier,remaining == 1:橙色 + 「今日仅剩 1 次查询」
 * - free tier,remaining >= 2:琥珀 + 「今日剩余 N 次查询」
 * - 沙箱模式:角标「沙箱」便于识别
 * - role="status" + aria-live="polite" + data-quota-state 属性
 */
import { useTranslation } from "react-i18next";

import { useApiQuota } from "@/features/useApiQuota";
import type { QuotaDTO } from "@/lib/api";

export interface QuotaBannerProps {
  stateOverride?: QuotaDTO | null;
  /** 静默测试时禁用轮询(单测用) */
  silent?: boolean;
}

export function QuotaBanner({ stateOverride }: QuotaBannerProps) {
  const { t } = useTranslation();
  const query = useApiQuota();

  const state: QuotaDTO | null =
    stateOverride !== undefined ? stateOverride : (query.data ?? null);
  if (state === null) return null;

  // pro 用户无限,不展示
  if (state.tier === "pro" || state.remaining === -1) return null;

  const remaining = state.remaining;
  const palette = paletteFor(remaining);
  const message = messageFor(remaining, t);

  return (
    <div
      role="status"
      aria-live="polite"
      data-quota-state={stateOf(remaining)}
      className={`border-y px-4 py-2 text-sm flex items-center gap-2 ${palette.cls}`}
    >
      <span aria-hidden="true" className={palette.icon}>
        {palette.glyph}
      </span>
      <span className="flex-1">{message}</span>
      {state.is_sandbox ? (
        <span className="text-xs text-slate-500 font-mono">[沙箱]</span>
      ) : null}
      {remaining === 0 ? (
        <a
          href="/subscribe"
          data-upgrade-link="quota-exhausted"
          className="text-xs underline text-amber-400 hover:text-amber-300"
        >
          {t("marketing.upgradeCta") || "升级 Pro"}
        </a>
      ) : null}
    </div>
  );
}

function stateOf(remaining: number): "ok" | "low" | "exhausted" {
  if (remaining <= 0) return "exhausted";
  if (remaining === 1) return "low";
  return "ok";
}

function paletteFor(remaining: number): {
  cls: string;
  icon: string;
  glyph: string;
} {
  if (remaining <= 0) {
    return {
      cls: "bg-red-950/30 border-red-800/50 text-red-200",
      icon: "text-red-400",
      glyph: "[!]",
    };
  }
  if (remaining === 1) {
    return {
      cls: "bg-orange-950/30 border-orange-800/50 text-orange-200",
      icon: "text-orange-400",
      glyph: "[!]",
    };
  }
  return {
    cls: "bg-amber-950/30 border-amber-800/50 text-amber-200",
    icon: "text-amber-400",
    glyph: "[i]",
  };
}

function messageFor(remaining: number, t: (k: string) => string): string {
  if (remaining <= 0) {
    return t("quota.exhausted") || "今日查询配额已用完,请明日再来或升级 Pro";
  }
  return (
    t("quota.remaining", { n: remaining }) ||
    `今日剩余 ${remaining} 次查询(免费版每日上限 ${3} 次)`
  );
}

/** 单测 helper:给定 QuotaDTO 返状态字符串(便于脚本断言)。 */
export function describeQuotaState(state: QuotaDTO): string {
  if (state.tier === "pro" || state.remaining === -1) return "pro";
  if (state.remaining <= 0) return "exhausted";
  if (state.remaining === 1) return "low";
  return "ok";
}
