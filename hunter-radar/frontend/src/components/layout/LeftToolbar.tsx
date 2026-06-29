/**
 * FE-103: 左侧垂直工具栏 — Analyzer Lenses
 *
 * PRD §2.2: 分析器透镜快捷控制面板
 * - 每个图标切换一层可视化数据(期权/做空/背离/内部人)
 * - 点击在主画布叠加/隐藏对应指标层
 * - < 768px 时下沉为底部 Bottom Sheet(FE-107)
 */
import { useTranslation } from "react-i18next";
import { useUIStore, type AnalyzerLayer } from "@/store/uiStore";

interface LensDef {
  layer: AnalyzerLayer;
  /** 纯文字图标(避免 emoji) */
  icon: string;
  i18nKey: string;
}

const LENSES: LensDef[] = [
  { layer: "options", icon: "OP", i18nKey: "modules.options" },
  { layer: "short", icon: "SH", i18nKey: "modules.short" },
  { layer: "divergence", icon: "DV", i18nKey: "modules.divergence" },
  { layer: "insider", icon: "IN", i18nKey: "modules.insider" },
];

export function LeftToolbar() {
  const { t } = useTranslation();
  const { activeOverlays, toggleOverlay, leftToolbarCollapsed, toggleLeftToolbar } = useUIStore();

  return (
    <div className="flex flex-col items-center py-3 gap-1">
      {/* 折叠/展开按钮 */}
      <button
        onClick={toggleLeftToolbar}
        className="w-9 h-9 rounded flex items-center justify-center text-xs text-slate-500 hover:bg-slate-800 hover:text-slate-300 mb-2"
        aria-label={leftToolbarCollapsed ? "expand toolbar" : "collapse toolbar"}
        title={leftToolbarCollapsed ? "expand" : "collapse"}
      >
        {leftToolbarCollapsed ? "»" : "«"}
      </button>

      {/* 图层切换按钮 */}
      {LENSES.map(({ layer, icon, i18nKey }) => {
        const active = activeOverlays[layer];
        return (
          <button
            key={layer}
            onClick={() => toggleOverlay(layer)}
            className={[
              "w-10 h-10 rounded flex flex-col items-center justify-center gap-0.5",
              "text-[10px] font-mono transition-colors",
              active
                ? "bg-sky-900/60 text-sky-300 border border-sky-700"
                : "text-slate-500 hover:bg-slate-800 hover:text-slate-300 border border-transparent",
            ].join(" ")}
            title={t(i18nKey)}
            aria-label={`${t(i18nKey)} ${active ? "ON" : "OFF"}`}
            aria-pressed={active}
          >
            <span className="text-sm font-bold leading-none">{icon}</span>
            {!leftToolbarCollapsed && (
              <span className="leading-none">{active ? "ON" : ""}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * FE-107: 移动端底部工具栏(从 LeftToolbar 拆分)
 * < 768px 时显示为固定底部栏
 */
export function MobileBottomToolbar() {
  const { activeOverlays, toggleOverlay } = useUIStore();

  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#0f172a] border-t border-slate-800 px-2 py-2 flex items-center justify-around">
      {LENSES.map(({ layer, icon, i18nKey }) => {
        const active = activeOverlays[layer];
        return (
          <button
            key={layer}
            onClick={() => toggleOverlay(layer)}
            className={[
              "flex flex-col items-center gap-0.5 px-3 py-1 rounded",
              "text-[10px] font-mono",
              active ? "text-sky-300" : "text-slate-500",
            ].join(" ")}
            aria-label={i18nKey}
            aria-pressed={active}
          >
            <span className="text-base font-bold">{icon}</span>
          </button>
        );
      })}
    </div>
  );
}
