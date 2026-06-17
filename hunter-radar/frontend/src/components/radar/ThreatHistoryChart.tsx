import { useMemo } from "react";

export type ThreatHistoryPoint = {
  date: string;
  total: number; // EMA 后
  total_raw: number; // EMA 前
  lifecycle?: "init" | "red" | "yellow" | "gray" | "green";
};

interface ThreatHistoryChartProps {
  data: ThreatHistoryPoint[];
  threshold: number;
  width?: number;
  height?: number;
  days?: number;
}

const lifecycleStroke: Record<string, string> = {
  init: "#64748b",
  red: "#dc2626",
  yellow: "#f59e0b",
  gray: "#94a3b8",
  green: "#10b981",
};

/** 90 日 Threat Score 轨迹纯 SVG 折线图(FE-032 / BD-066)。
 *
 * 严格规则:
 * 1. 无 ECharts 依赖(包体 < 200KB gzip,frontend-plan §7.1)
 * 2. 显示 EMA 后分主线 + 阈值标线 + lifecycle 颜色编码
 * 3. 数据缺失(< 2 点)显示占位文案,不渲染假图
 */
export function ThreatHistoryChart({
  data,
  threshold,
  width = 480,
  height = 200,
  days = 90,
}: ThreatHistoryChartProps) {
  const layout = useMemo(() => {
    if (!data || data.length < 2) return null;

    // 排序 + 截取最近 N 日
    const sorted = [...data]
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-days);

    const padTop = 16;
    const padBottom = 28;
    const padLeft = 32;
    const padRight = 8;
    const innerW = width - padLeft - padRight;
    const innerH = height - padTop - padBottom;

    const n = sorted.length;
    const xAt = (i: number) => padLeft + (i / (n - 1)) * innerW;
    const yAt = (v: number) => padTop + (1 - Math.max(0, Math.min(100, v)) / 100) * innerH;

    // 主线(EMA 后)
    const mainPath = sorted
      .map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.total).toFixed(1)}`)
      .join(" ");

    // 阈值标线
    const thresholdY = yAt(threshold);

    // Y 轴刻度
    const yTicks = [0, 50, 70, 100];

    // X 轴日期标签(只显示首末 + 1/2 三个点)
    const xLabels = sorted.length >= 3 ? [0, Math.floor(n / 2), n - 1] : [0, n - 1];

    return {
      sorted,
      mainPath,
      thresholdY,
      yTicks,
      xLabels,
      xAt,
      yAt,
      padLeft,
    };
  }, [data, threshold, width, height, days]);

  if (!layout) {
    return (
      <div
        className="flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4"
        style={{ width, height: height * 0.7 }}
      >
        轨迹数据积累中(约需 {days} 个交易日),暂不可绘制
      </div>
    );
  }

  const { sorted, mainPath, thresholdY, yTicks, xLabels, xAt, yAt, padLeft } = layout;

  return (
    <div className="flex flex-col">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`近 ${days} 日 Threat Score 轨迹`}
      >
        {/* Y 轴刻度线 */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={padLeft}
              y1={yAt(v)}
              x2={width - 8}
              y2={yAt(v)}
              stroke="#1e293b"
              strokeWidth={1}
            />
            <text x={4} y={yAt(v) + 3} fontSize={9} fill="#64748b">
              {v}
            </text>
          </g>
        ))}

        {/* 阈值标线(dashed) */}
        <line
          x1={padLeft}
          y1={thresholdY}
          x2={width - 8}
          y2={thresholdY}
          stroke="#475569"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <text
          x={width - 36}
          y={thresholdY - 3}
          fontSize={9}
          fill="#94a3b8"
        >
          {threshold}
        </text>

        {/* 主线 */}
        <path
          d={mainPath}
          stroke="#cbd5e1"
          strokeWidth={1.5}
          fill="none"
          strokeLinejoin="round"
        />

        {/* 数据点(lifecycle 颜色编码) */}
        {sorted.map((p, i) => {
          const c = p.lifecycle ? lifecycleStroke[p.lifecycle] : "#cbd5e1";
          return (
            <circle
              key={p.date}
              cx={xAt(i)}
              cy={yAt(p.total)}
              r={2}
              fill={c}
              stroke="#0f172a"
              strokeWidth={0.5}
            >
              <title>
                {p.date} · EMA {p.total.toFixed(1)} · 原始 {p.total_raw.toFixed(1)}
                {p.lifecycle ? ` · ${p.lifecycle}` : ""}
              </title>
            </circle>
          );
        })}

        {/* X 轴日期标签 */}
        {xLabels.map((i) => (
          <text
            key={i}
            x={xAt(i)}
            y={height - 8}
            fontSize={9}
            fill="#64748b"
            textAnchor={i === 0 ? "start" : i === sorted.length - 1 ? "end" : "middle"}
          >
            {sorted[i].date.slice(5)}
          </text>
        ))}
      </svg>
      <div className="text-xs text-slate-500 mt-1">
        纵轴:Threat Score (EMA) · 主线:EMA 后分 · 阈值:{threshold}
      </div>
    </div>
  );
}
