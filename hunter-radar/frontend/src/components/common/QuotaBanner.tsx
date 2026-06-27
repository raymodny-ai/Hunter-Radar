/** §6.3 FE-064 Quota banner — always null (payment features removed). */

export interface QuotaBannerProps {
  stateOverride?: unknown;
  silent?: boolean;
}

/** Always returns null — payments removed. */
export function QuotaBanner(_props: QuotaBannerProps): null {
  return null;
}

export function describeQuotaState(): string {
  return "pro";
}
