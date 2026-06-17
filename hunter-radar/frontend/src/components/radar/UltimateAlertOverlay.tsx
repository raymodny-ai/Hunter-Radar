import { useEffect, useRef } from "react";

import { Disclaimer } from "@/components/common/Disclaimer";

export type UltimateAlertDTO = {
  triggered_at: string;
  trade_date: string;
  symbol: string;
  threat_score: number;
  raw_score: number;
  ema_score: number;
  modules_active: string[];
  regime: "normal" | "panic";
  consecutive_days: number;
};

interface UltimateAlertOverlayProps {
  open: boolean;
  alert: UltimateAlertDTO | null;
  onClose: () => void;
}

/** 终极警报全屏覆盖层(BD-062/064 + frontend-plan §5.4.2 + CR-009/CR-010)。
 *
 * 严格规则:
 * 1. 严禁自动消失;必须用户主动点击「我已了解」按钮
 * 2. 必含「仅供参考 / 不构成投资建议」兜底文案
 * 3. 不渲染 emoji;颜色 + 文字双编码
 * 4. 键盘可达:Tab 聚焦「我已了解」按钮
 */
export function UltimateAlertOverlay({ open, alert, onClose }: UltimateAlertOverlayProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  // 打开时自动 focus「我已了解」按钮,提升键盘可达性
  useEffect(() => {
    if (open) {
      closeRef.current?.focus();
    }
  }, [open]);

  if (!open || !alert) return null;

  const isPanic = alert.regime === "panic";
  const modText = alert.modules_active.length
    ? alert.modules_active.join("、")
    : "未识别";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ultimate-alert-title"
      aria-describedby="ultimate-alert-desc"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
    >
      <div className="bg-slate-900 border border-hunter-red/60 rounded-lg max-w-lg w-full p-6 shadow-2xl">
        <header className="border-b border-slate-800 pb-3 mb-4">
          <div className="text-xs uppercase tracking-wider text-hunter-red font-mono">
            终极警报 · Ultimate Alert
          </div>
          <h2
            id="ultimate-alert-title"
            className="text-lg font-bold text-slate-100 mt-1"
          >
            {alert.symbol} 检测到多维度做空筹码共振
          </h2>
        </header>

        <div id="ultimate-alert-desc" className="space-y-3 text-sm text-slate-300">
          <p>
            <span className="text-slate-500">交易日:</span>
            <span className="font-mono ml-2">{alert.trade_date}</span>
          </p>
          <p>
            <span className="text-slate-500">EMA 后总分:</span>
            <span className="font-mono ml-2 text-hunter-red font-bold">
              {alert.ema_score.toFixed(1)}
            </span>
            <span className="text-slate-500 text-xs ml-2">
              (原始 {alert.raw_score.toFixed(1)})
            </span>
          </p>
          <p>
            <span className="text-slate-500">连续触发:</span>
            <span className="font-mono ml-2">{alert.consecutive_days} 个交易日</span>
          </p>
          <p>
            <span className="text-slate-500">活跃模块:</span>
            <span className="ml-2">{modText}</span>
          </p>
          <p>
            <span className="text-slate-500">市场状态:</span>
            <span className="ml-2">
              {isPanic ? "恐慌模式(阈值上调)" : "正常波动"}
            </span>
          </p>
        </div>

        <footer className="mt-6 pt-4 border-t border-slate-800 space-y-3">
          {/* m5t5 合规文案收口(FE-062/063):用 Disclaimer modal 变体 + 滚动,避免 dialog 被长文撑高 */}
          <Disclaimer variant="modal" scrollable maxHeightPx={120} />
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="w-full py-2 px-4 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-hunter-red"
          >
            我已了解
          </button>
        </footer>
      </div>
    </div>
  );
}
