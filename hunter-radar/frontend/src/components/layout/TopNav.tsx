/**
 * FE-101: 顶部全局导航栏
 *
 * PRD §2.1: 全局中枢
 * - 左侧:Logo + 导航链接
 * - 中间:全局搜索框(SearchBox)
 * - 右侧:系统状态灯带(绿/琥珀/红) + 日志开关
 */
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { SearchBox } from "./SearchBox";
import { useDataStatus } from "@/features/useDataStatus";
import { useUIStore } from "@/store/uiStore";

const STATUS_DOT: Record<string, string> = {
  ready: "bg-emerald-500",
  warming: "bg-amber-500 animate-pulse",
  stale: "bg-amber-600 animate-pulse",
  error: "bg-red-500",
};

export function TopNav() {
  const { t } = useTranslation();
  const status = useDataStatus();
  const [logVisible, setLogVisible] = useState(false);
  const { setRightSidebarOpen, rightSidebarOpen } = useUIStore();

  const dot = STATUS_DOT[status.data?.status ?? "warming"] ?? STATUS_DOT.warming;

  // 暴露 logVisible setter 给外部(LogPanel 在 __root 中)
  // 暂时用内部 state,后续可提升到 store
  (window as unknown as Record<string, unknown>).__hunterLogToggle = setLogVisible;

  return (
    <div className="flex items-center gap-4 px-4 py-2.5">
      {/* ── Logo + 导航 ──────────────────────────────── */}
      <Link to="/" className="font-bold text-base tracking-wider shrink-0 hover:text-white">
        {t("app.name")}
      </Link>

      <nav className="hidden sm:flex gap-3 text-sm text-slate-400 shrink-0">
        <NavLink to="/screener" label={t("routes.screener")} />
        <NavLink to="/basket" label={t("routes.basket")} />
        <NavLink to="/alerts" label={t("routes.alerts")} />
        <NavLink to="/logs" label="Logs" />
      </nav>

      {/* ── 搜索框 ──────────────────────────────────── */}
      <div className="flex-1 flex justify-center">
        <SearchBox />
      </div>

      {/* ── 右侧:状态灯 + 工具按钮 ─────────────────── */}
      <div className="flex items-center gap-2 shrink-0">
        {/* 数据状态灯 */}
        <div
          className="flex items-center gap-1.5"
          title={status.data?.reason ?? "loading"}
          aria-label={t("dataStatus.label") || "data status"}
        >
          <span className={`w-2 h-2 rounded-full ${dot}`} />
          <span className="text-xs text-slate-500 hidden lg:inline">
            {status.data?.status ?? "…"}
          </span>
        </div>

        {/* 右侧边栏切换(xl 以下显示) */}
        <button
          onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
          className={[
            "xl:hidden text-xs px-2 py-1 rounded border",
            rightSidebarOpen
              ? "bg-sky-900/50 border-sky-700 text-sky-200"
              : "bg-slate-800/50 border-slate-700 text-slate-400 hover:text-slate-200",
          ].join(" ")}
          aria-label="toggle sidebar"
          title="Toggle sidebar"
        >
          {rightSidebarOpen ? "✕" : "☰"}
        </button>

        {/* 日志面板开关（仅触发右下角小弹窗，完整页面走顶部 NavLink /logs） */}
        <button
          onClick={() => setLogVisible((v) => !v)}
          className={[
            "text-xs px-2 py-1 rounded font-mono border",
            logVisible
              ? "bg-sky-900/50 border-sky-700 text-sky-200"
              : "bg-slate-800/50 border-slate-700 text-slate-400 hover:text-slate-200",
          ].join(" ")}
          title={logVisible ? "关闭实时弹窗" : "打开实时弹窗(完整页面: /logs)"}
        >
          ⚡
        </button>
      </div>
    </div>
  );
}

function NavLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="hover:text-white transition-colors"
      activeProps={{ className: "text-white font-medium" }}
    >
      {label}
    </Link>
  );
}
