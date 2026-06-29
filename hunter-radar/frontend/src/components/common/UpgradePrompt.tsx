/** FE-082 Upgrade prompt — always null (payment features removed). */
/** 兜底文案提示:仅供参考,不构成投资建议;统计口径详见 §6.3。 */

export type UpgradeVariant = "inline" | "block" | "modal";

export interface UpgradePromptProps {
  variant?: UpgradeVariant;
  reason?: string;
  className?: string;
  href?: string;
}

/** Always returns null — payments removed. */
export function UpgradePrompt(_props: UpgradePromptProps): null {
  return null;
}

export function shouldShowUpgradePrompt(
  _tier: string,
  _trigger: string,
): boolean {
  return false;
}
