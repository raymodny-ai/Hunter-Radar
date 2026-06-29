/**
 * FE-108: Zustand UI 状态 Store
 *
 * 管理客户端 UI 易失状态:
 * - leftToolbarCollapsed: 左侧工具栏折叠状态
 * - rightSidebarTab: 右侧边栏当前激活 Tab
 * - rightSidebarOpen: 右侧边栏是否展开
 * - activeOverlays: 左侧工具栏激活的图层(期权/做空/背离/内部人)
 *
 * localStorage 持久化,尊重 SSR。
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SidebarTab = "watchlist" | "alerts" | "copilot";
export type AnalyzerLayer = "options" | "short" | "divergence" | "insider";

export interface UIState {
  // ── 布局状态 ──────────────────────────────────
  leftToolbarCollapsed: boolean;
  rightSidebarTab: SidebarTab;
  rightSidebarOpen: boolean;

  // ── 图层状态 ──────────────────────────────────
  activeOverlays: Record<AnalyzerLayer, boolean>;

  // ── Actions ───────────────────────────────────
  toggleLeftToolbar: () => void;
  setLeftToolbarCollapsed: (collapsed: boolean) => void;
  setRightSidebarTab: (tab: SidebarTab) => void;
  setRightSidebarOpen: (open: boolean) => void;
  toggleOverlay: (layer: AnalyzerLayer) => void;
  setOverlay: (layer: AnalyzerLayer, active: boolean) => void;
}

const DEFAULT_OVERLAYS: Record<AnalyzerLayer, boolean> = {
  options: true,
  short: true,
  divergence: true,
  insider: true,
};

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      leftToolbarCollapsed: false,
      rightSidebarTab: "watchlist" as SidebarTab,
      rightSidebarOpen: false,
      activeOverlays: { ...DEFAULT_OVERLAYS },

      toggleLeftToolbar: () =>
        set((s) => ({ leftToolbarCollapsed: !s.leftToolbarCollapsed })),

      setLeftToolbarCollapsed: (collapsed) =>
        set({ leftToolbarCollapsed: collapsed }),

      setRightSidebarTab: (tab) =>
        set({ rightSidebarTab: tab, rightSidebarOpen: true }),

      setRightSidebarOpen: (open) =>
        set({ rightSidebarOpen: open }),

      toggleOverlay: (layer) =>
        set((s) => ({
          activeOverlays: {
            ...s.activeOverlays,
            [layer]: !s.activeOverlays[layer],
          },
        })),

      setOverlay: (layer, active) =>
        set((s) => ({
          activeOverlays: { ...s.activeOverlays, [layer]: active },
        })),
    }),
    {
      name: "hunter-ui-store",
      partialize: (state) => ({
        leftToolbarCollapsed: state.leftToolbarCollapsed,
        rightSidebarTab: state.rightSidebarTab,
        activeOverlays: state.activeOverlays,
      }),
    },
  ),
);
