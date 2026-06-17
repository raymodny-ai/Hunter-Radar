/** BD-101 PWA 安装提示 hook(Chrome / Edge / Android + iOS Safari 双适配)。
 *
 * 数据源:
 * - Chrome/Edge/Android:监听 `beforeinstallprompt` 事件,捕获 BeforeInstallPromptEvent
 * - iOS Safari:无 beforeinstallprompt,需通过 UA + !standalone 识别
 *   引导用户「分享 → 添加到主屏」
 *
 * 行为:
 * - 沙箱模式(localhost / 127.0.0.1)不弹 — Chrome 在 localhost 不会触发 install 事件
 * - 已安装 standalone(独立窗口)不弹 — `display-mode: standalone` || `navigator.standalone`
 * - 7 天内 dismiss 不再弹 — localStorage `hr_pwa_dismissed_until` 存 epoch ms
 *
 * 沙箱降级:
 * - 无 `window.matchMedia` 时 isStandalone 返 false
 * - 无 `localStorage` 时 dismiss 静默 no-op
 */
import { useCallback, useEffect, useState } from "react";

const DISMISS_KEY = "hr_pwa_dismissed_until";
const DISMISS_DAYS = 7;

// Chrome 派发的事件类型(未在 lib.dom.d.ts 中)
interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
  prompt(): Promise<void>;
}

function isStandaloneMode(): boolean {
  if (typeof window === "undefined") return false;
  // 1. 标准 display-mode media query
  const mql =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(display-mode: standalone)")
      : null;
  if (mql?.matches) return true;
  // 2. iOS Safari navigator.standalone
  const nav = window.navigator as Navigator & { standalone?: boolean };
  return nav.standalone === true;
}

function isIOSSafari(): boolean {
  if (typeof window === "undefined") return false;
  const ua = window.navigator.userAgent;
  // iOS: iPhone/iPad/iPod + Safari(排除 Chrome iOS / CriOS / FxiOS)
  const isiOS = /iPad|iPhone|iPod/.test(ua) && !("MSStream" in window);
  const isSafari = /Safari\//.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
  return isiOS && isSafari;
}

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
    // localStorage 写入失败(隐私模式 / 容量超)静默
  }
}

export interface UsePWAInstallResult {
  /** Chrome/Edge/Android 是否可以触发安装;null 表示未知(等待事件) */
  installPrompt: BeforeInstallPromptEvent | null;
  /** iOS Safari 走「分享 → 添加到主屏」手动引导 */
  isIOS: boolean;
  /** 当前是否已安装为独立应用(不弹) */
  isStandalone: boolean;
  /** 7 天内已关闭(不弹) */
  isDismissed: boolean;
  /** 触发原生安装弹窗(仅 Chrome/Edge/Android 有效);返 outcome */
  install(): Promise<"accepted" | "dismissed" | "unavailable">;
  /** 用户主动关闭(7 天内不再弹) */
  dismiss(): void;
}

export function usePWAInstall(): UsePWAInstallResult {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandaloneState, setIsStandalone] = useState<boolean>(false);
  const [isDismissedState, setIsDismissed] = useState<boolean>(false);

  // 初始化 standalone + dismissed 状态
  useEffect(() => {
    setIsStandalone(isStandaloneMode());
    setIsDismissed(isDismissed());
  }, []);

  // 监听 beforeinstallprompt
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = (e: Event) => {
      // Chrome 67+ 派发,需 preventDefault 阻止自动弹
      e.preventDefault();
      setInstallPrompt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler as EventListener);
    // 监听 appinstalled(用户接受后清状态)
    const installedHandler = () => setInstallPrompt(null);
    window.addEventListener("appinstalled", installedHandler);
    return () => {
      window.removeEventListener("beforeinstallprompt", handler as EventListener);
      window.removeEventListener("appinstalled", installedHandler);
    };
  }, []);

  const install = useCallback(async (): Promise<"accepted" | "dismissed" | "unavailable"> => {
    if (!installPrompt) return "unavailable";
    await installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    setInstallPrompt(null);
    return choice.outcome;
  }, [installPrompt]);

  const dismiss = useCallback(() => {
    persistDismiss();
    setIsDismissed(true);
  }, []);

  return {
    installPrompt,
    isIOS: isIOSSafari(),
    isStandalone: isStandaloneState,
    isDismissed: isDismissedState,
    install,
    dismiss,
  };
}
