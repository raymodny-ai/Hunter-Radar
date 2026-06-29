/**
 * FE-100: 四区 Grid 布局骨架 — AppShell
 *
 * PRD §2: 严格遵循 TradingView 四区模块化拓扑规范
 * - 顶部全局导航栏 (Top Toolbar)
 * - 左侧垂直工具栏 (Left Toolbar)
 * - 主内容可视化画布 (Main Charting Canvas)
 * - 右侧功能侧边栏 (Right Widget Bar)
 *
 * 响应式断点:
 * - xl (>1280px): 完整三栏布局
 * - md (>768px): 右侧边栏折叠为抽屉
 * - <768px: 垂直单列 + 底部工具栏
 */
import type { ReactNode } from "react";
import { useUIStore } from "@/store/uiStore";

interface AppShellProps {
  topNav: ReactNode;
  leftToolbar: ReactNode;
  rightSidebar: ReactNode;
  banners?: ReactNode;
  footer: ReactNode;
  children: ReactNode;
}

export function AppShell({
  topNav,
  leftToolbar,
  rightSidebar,
  banners,
  footer,
  children,
}: AppShellProps) {
  const { leftToolbarCollapsed, rightSidebarOpen } = useUIStore();

  return (
    <div className="min-h-screen flex flex-col bg-[#0f172a] text-slate-200">
      {/* ── 顶部导航栏(全宽) ───────────────────────────── */}
      <header className="z-30 border-b border-slate-800 bg-[#0f172a]/95 backdrop-blur-sm">
        {topNav}
      </header>

      {/* ── 全局横幅区(DataStatus / Regime / Quota / PWA) ── */}
      {banners}

      {/* ── 主体三栏区 ─────────────────────────────────── */}
      <div
        className={[
          "flex-1 flex overflow-hidden",
          // 主容器占满剩余高度
          "h-[calc(100vh-var(--header-h,56px))]",
        ].join(" ")}
      >
        {/* ── 左侧工具栏 ────────────────────────────────── */}
        <aside
          className={[
            "hidden md:flex flex-col border-r border-slate-800 bg-[#0f172a]",
            "transition-[width] duration-200 ease-in-out shrink-0",
            leftToolbarCollapsed ? "w-12" : "w-14 xl:w-16",
          ].join(" ")}
          aria-label="analyzer-lenses"
        >
          {leftToolbar}
        </aside>

        {/* ── 主画布区 ──────────────────────────────────── */}
        <main
          className={[
            "flex-1 overflow-y-auto overflow-x-hidden",
            "px-4 py-5 md:px-6 md:py-6",
            // 移动端底部留出工具栏空间
            "pb-20 md:pb-6",
          ].join(" ")}
          role="main"
        >
          <div className="max-w-screen-2xl w-full mx-auto">{children}</div>
        </main>

        {/* ── 右侧边栏 ─────────────────────────────────── */}
        {/* xl: inline flex; md-xl: overlay drawer */}
        <aside
          className={[
            "flex-col border-l border-slate-800 bg-[#0f172a]",
            "transition-[width,transform] duration-200 ease-in-out shrink-0",
            // xl: inline always
            "hidden xl:flex",
            // md: overlay drawer mode
            rightSidebarOpen
              ? "!flex fixed xl:static inset-y-0 right-0 z-50 w-80 shadow-2xl"
              : "hidden",
          ].join(" ")}
          aria-label="right-sidebar"
        >
          {rightSidebarOpen && rightSidebar}
        </aside>

        {/* md drawer backdrop */}
        {rightSidebarOpen && (
          <div
            className="xl:hidden fixed inset-0 z-40 bg-black/50"
            onClick={() => useUIStore.getState().setRightSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
      </div>

      {/* ── 底部页脚 ──────────────────────────────────── */}
      <footer className="border-t border-slate-800 px-4 py-3 text-xs text-slate-500 shrink-0">
        {footer}
      </footer>

      {/* ── 移动端底部工具栏(FE-107 占位,在 LeftToolbar 中实现) ── */}
    </div>
  );
}
