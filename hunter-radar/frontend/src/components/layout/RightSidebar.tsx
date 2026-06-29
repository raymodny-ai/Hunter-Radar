/**
 * FE-104: 右侧功能侧边栏 — Tabs 抽屉
 *
 * PRD §2.4: 多标签切换抽屉结构
 * - Tab 1: Watchlist(自选篮子微缩面板,FE-105)
 * - Tab 2: Alerts Center(预警流面板,FE-106)
 * - Tab 3: AI Copilot(LLM 智能助手面板)
 * - Tab 状态由 Zustand 持久化
 */
import { useTranslation } from "react-i18next";
import { useUIStore, type SidebarTab } from "@/store/uiStore";

interface TabDef {
  key: SidebarTab;
  i18nKey: string;
  shortLabel: string;
}

const TABS: TabDef[] = [
  { key: "watchlist", i18nKey: "sidebar.watchlist", shortLabel: "WL" },
  { key: "alerts", i18nKey: "sidebar.alerts", shortLabel: "AL" },
  { key: "copilot", i18nKey: "sidebar.copilot", shortLabel: "AI" },
];

export function RightSidebar() {
  const { t } = useTranslation();
  const { rightSidebarTab, setRightSidebarTab, setRightSidebarOpen } = useUIStore();

  return (
    <div className="flex flex-col h-full w-80">
      {/* ── Tab 栏 ────────────────────────────────────── */}
      <div className="flex items-center border-b border-slate-800 shrink-0">
        {TABS.map(({ key, i18nKey, shortLabel }) => (
          <button
            key={key}
            onClick={() => setRightSidebarTab(key)}
            className={[
              "flex-1 py-2.5 text-xs font-medium transition-colors",
              rightSidebarTab === key
                ? "text-sky-300 border-b-2 border-sky-400 bg-slate-900/50"
                : "text-slate-500 hover:text-slate-300",
            ].join(" ")}
            aria-selected={rightSidebarTab === key}
            role="tab"
          >
            <span className="sm:hidden">{shortLabel}</span>
            <span className="hidden sm:inline">{t(i18nKey) || shortLabel}</span>
          </button>
        ))}
        <button
          onClick={() => setRightSidebarOpen(false)}
          className="px-2 py-2.5 text-slate-500 hover:text-slate-300 text-sm"
          aria-label="close sidebar"
        >
          ✕
        </button>
      </div>

      {/* ── Tab 内容区 ────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {rightSidebarTab === "watchlist" && <WatchlistPanel />}
        {rightSidebarTab === "alerts" && <AlertsStreamPanel />}
        {rightSidebarTab === "copilot" && <CopilotPanel />}
      </div>
    </div>
  );
}

/**
 * FE-105: Watchlist 微缩面板(右侧边栏)
 * 紧凑列表展示篮子成员的最新 Threat Score + 红绿灯状态
 */
function WatchlistPanel() {
  const { t } = useTranslation();
  return (
    <div className="p-3 text-sm text-slate-400">
      <p className="text-xs text-slate-500 mb-3">
        {t("sidebar.watchlistHint") || "自选篮子成员的实时风险状态将在 M3 对接。"}
      </p>
      {/* FE-105 骨架占位,M3 阶段填充实际数据 */}
      <div className="space-y-2">
        {["AAPL", "TSLA", "QQQ"].map((ticker) => (
          <div
            key={ticker}
            className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded px-3 py-2"
          >
            <span className="font-mono font-bold text-slate-300">{ticker}</span>
            <span className="text-xs text-slate-500">— —</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * FE-106: Alerts Center 预警流面板(右侧边栏)
 * 时间倒序滚动,点击跳转详情页
 */
function AlertsStreamPanel() {
  const { t } = useTranslation();
  return (
    <div className="p-3 text-sm text-slate-400">
      <p className="text-xs text-slate-500 mb-3">
        {t("sidebar.alertsHint") || "预警事件流将在 M3 对接 alerts API。"}
      </p>
      {/* FE-106 骨架占位 */}
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-slate-900 border border-slate-800 rounded px-3 py-2"
          >
            <div className="text-xs text-slate-500">
              {t("sidebar.noAlerts") || "暂无预警事件"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Copilot Tab:指向 LlmPanel 的入口提示
 * 实际 LLM 交互在 LlmPanel 组件中(已有)
 */
function CopilotPanel() {
  const { t } = useTranslation();
  return (
    <div className="p-3 text-sm text-slate-400">
      <p className="text-xs text-slate-500">
        {t("sidebar.copilotHint") ||
          "进入标的详情页后,点击右上角 LLM 分析按钮启动 AI Copilot。"}
      </p>
    </div>
  );
}
