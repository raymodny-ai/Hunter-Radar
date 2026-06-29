/**
 * FE-123: Insider Action Timeline — 内部人交易掩护时间轴
 *
 * 挂载于图表 X 轴下方:
 * - C-level 减持:红色倒三角
 * - 点击弹出 Popover(职务/方向/数量/均价)
 * - ETF 标的整条灰态
 */
import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";

export interface InsiderAction {
  date: string;
  person_name: string;
  title: string;
  direction: "buy" | "sell";
  shares: number;
  price_per_share: number;
  is_c_level: boolean;
}

export interface InsiderTimelineProps {
  actions: InsiderAction[] | undefined;
  isEtf?: boolean;
  className?: string;
}

export function InsiderTimeline({
  actions,
  isEtf = false,
  className,
}: InsiderTimelineProps) {
  const { t } = useTranslation();
  const [popoverIdx, setPopoverIdx] = useState<number | null>(null);

  const sorted = useMemo(() => {
    if (!actions) return [];
    return [...actions].sort((a, b) => b.date.localeCompare(a.date));
  }, [actions]);

  if (!sorted || sorted.length === 0) {
    return (
      <div className={`text-xs text-slate-500 py-2 ${className || ""}`}>
        {t("charts.insider.noData")}
      </div>
    );
  }

  return (
    <div className={`${isEtf ? "opacity-40 pointer-events-none" : ""} ${className || ""}`}>
      <div className="flex items-center gap-1 mb-2">
        <h4 className="text-xs text-slate-400 font-semibold">
          {t("charts.insider.title")}
        </h4>
        {isEtf && (
          <span className="text-[10px] text-slate-600 ml-1">
            ({t("charts.insider.etfDisabled")})
          </span>
        )}
      </div>

      <div className="flex items-end gap-1 overflow-x-auto pb-1">
        {sorted.map((a, i) => {
          const isSell = a.direction === "sell";
          const isOpen = popoverIdx === i;

          return (
            <div key={`${a.date}-${i}`} className="relative flex-shrink-0">
              {/* 倒三角 / 正三角 */}
              <button
                onClick={() => setPopoverIdx(isOpen ? null : i)}
                className="flex flex-col items-center cursor-pointer group"
                title={`${a.date} · ${a.person_name}`}
              >
                {isSell ? (
                  <svg width="14" height="16" viewBox="0 0 14 16">
                    <polygon
                      points="7,16 0,2 14,2"
                      fill={a.is_c_level ? "#FF5252" : "#ef4444"}
                      opacity={0.85}
                    />
                  </svg>
                ) : (
                  <svg width="14" height="16" viewBox="0 0 14 16">
                    <polygon
                      points="7,0 14,14 0,14"
                      fill="#10b981"
                      opacity={0.85}
                    />
                  </svg>
                )}
                <span className="text-[8px] text-slate-600 mt-0.5 font-mono">
                  {a.date.slice(5)}
                </span>
              </button>

              {/* Popover */}
              {isOpen && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 bg-slate-900 border border-slate-700 rounded-md p-3 text-xs text-slate-300 shadow-xl min-w-[180px]">
                  <button
                    className="absolute top-1 right-1.5 text-slate-500 hover:text-slate-300 text-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPopoverIdx(null);
                    }}
                  >
                    ✕
                  </button>
                  <div className="font-bold text-slate-200 mb-1">
                    {a.person_name}
                  </div>
                  <div className="text-slate-500 text-[10px] mb-2">{a.title}</div>
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-slate-500">{t("charts.insider.date")}:</span>
                      <span className="font-mono">{a.date}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">{t("charts.insider.direction")}:</span>
                      <span className={isSell ? "text-red-400" : "text-emerald-400"}>
                        {isSell ? t("charts.insider.sell") : t("charts.insider.buy")}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">{t("charts.insider.shares")}:</span>
                      <span className="font-mono">{a.shares.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">{t("charts.insider.price")}:</span>
                      <span className="font-mono">${a.price_per_share.toFixed(2)}</span>
                    </div>
                    {a.is_c_level && (
                      <div className="text-amber-400 text-[10px] mt-1">
                        ⚠ {t("charts.insider.cLevel")}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
