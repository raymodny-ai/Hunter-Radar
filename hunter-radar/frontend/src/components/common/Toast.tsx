/**
 * P1-05: 全局 Toast 通知系统
 *
 * - zustand 驱动，无额外依赖
 * - 支持 success / error / warning / info 四种变体
 * - aria-live="polite" 无障碍播报
 * - 自动 5s 消失，可手动关闭
 * - 与 lib/auth.ts 事件总线集成 (AuthToastBridge)
 */
import { useEffect } from "react";
import { create } from "zustand";
import { onAuthEvent } from "../../lib/auth";

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastState {
  toasts: ToastItem[];
  push: (message: string, variant?: ToastVariant) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, variant = "info") => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts.slice(-4), { id, message, variant }] }));
    // 自动消失
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 5000);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/** 命令式快捷调用 (非组件上下文) */
export const toast = {
  success: (msg: string) => useToastStore.getState().push(msg, "success"),
  error: (msg: string) => useToastStore.getState().push(msg, "error"),
  warning: (msg: string) => useToastStore.getState().push(msg, "warning"),
  info: (msg: string) => useToastStore.getState().push(msg, "info"),
};

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: "border-green-700/60 bg-green-900/90 text-green-100",
  error: "border-red-700/60 bg-red-900/90 text-red-100",
  warning: "border-yellow-700/60 bg-yellow-900/90 text-yellow-100",
  info: "border-slate-600/60 bg-slate-800/95 text-slate-100",
};

const VARIANT_ICONS: Record<ToastVariant, string> = {
  success: "✓",
  error: "✕",
  warning: "⚠",
  info: "ℹ",
};

/** Toast 渲染视口 — 挂载于 AppShell 根部 */
export function ToastViewport() {
  const { toasts, dismiss } = useToastStore();

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      role="status"
      className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm pointer-events-none"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-4 py-3 shadow-xl text-sm backdrop-blur animate-[slideIn_0.2s_ease-out] ${VARIANT_STYLES[t.variant]}`}
        >
          <span aria-hidden="true" className="font-bold shrink-0">
            {VARIANT_ICONS[t.variant]}
          </span>
          <span className="flex-1">{t.message}</span>
          <button
            onClick={() => dismiss(t.id)}
            aria-label="关闭通知"
            className="shrink-0 opacity-60 hover:opacity-100 focus:outline-none focus:ring-1 focus:ring-current rounded"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

/** 桥接 auth 事件 → toast (挂载于 AppShell) */
export function AuthToastBridge() {
  useEffect(() => {
    return onAuthEvent((event) => {
      if (event.type === "unauthorized") {
        toast.error(event.message);
      } else if (event.type === "rate-limit-warning") {
        toast.warning(event.message);
      }
    });
  }, []);
  return null;
}
