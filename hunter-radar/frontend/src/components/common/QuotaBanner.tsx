/** §6.3 FE-064 Quota banner — always null (payment features removed). */

export interface QuotaBannerProps {
  stateOverride?: unknown;
  silent?: boolean;
}

/** Quota state palette — returns CSS color for a given quota tier/state. */
export function paletteFor(state: string | null | undefined): string {
  switch (state) {
    case "free":
      return "#94a3b8"; // slate-400
    case "pro":
      return "#22d3ee"; // cyan-400
    case "exhausted":
      return "#f87171"; // red-400
    default:
      return "#64748b"; // slate-500
  }
}

/** Always returns null — payments removed. */
export function QuotaBanner(_props: QuotaBannerProps): null {
  return null;
}

/** Placeholder DOM hooks for accessibility audit (m5t8/m8t2). */
export const QUOTA_STATE_ATTR = "data-quota-state";
export const QUOTA_STATE_VALUE_PRO = "pro";

export function describeQuotaState(): string {
  return "pro";
}
