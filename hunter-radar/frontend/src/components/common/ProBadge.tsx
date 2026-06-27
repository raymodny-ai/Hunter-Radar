/** BD-105/FE-082 Pro badge — always null (payment features removed). */

export interface ProBadgeProps {
  variant?: "compact" | "full";
  className?: string;
  forceEn?: boolean;
}

/** Always returns null — payments removed. */
export function ProBadge(_props: ProBadgeProps): null {
  return null;
}

export function shouldShowProBadge(_tier: string): boolean {
  return false;
}
