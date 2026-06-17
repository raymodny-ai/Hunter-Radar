import { useEffect, useRef } from "react";

interface GaugeProps {
  value: number;          // EMA 后总分(决定颜色)
  raw: number;            // EMA 前原始分(供 inspector 对照)
  lifecycle: "init" | "red" | "yellow" | "gray" | "green";
  threshold: number;      // 红灯阈值
}

/** 圆形仪表盘 — 纯 SVG 渲染,无依赖,保证 Lighthouse 性能。 */
export function ThreatScoreGauge({ value, raw, lifecycle, threshold }: GaugeProps) {
  const ref = useRef<SVGSVGElement>(null);

  // 颜色映射
  const colorMap: Record<string, string> = {
    red: "#dc2626",
    yellow: "#f59e0b",
    gray: "#94a3b8",
    green: "#10b981",
    init: "#64748b",
  };
  const color = colorMap[lifecycle];

  // SVG 圆弧: 270° 弧(从 -135° 到 135°)
  const size = 200;
  const cx = size / 2;
  const cy = size / 2;
  const r = 80;
  const startAngle = -135;
  const endAngle = 135;
  const totalAngle = endAngle - startAngle; // 270
  const valueAngle = startAngle + (Math.max(0, Math.min(100, value)) / 100) * totalAngle;

  // 极坐标 → 直角
  const polar = (angleDeg: number) => {
    const rad = (angleDeg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const arc = (a1: number, a2: number) => {
    const p1 = polar(a1);
    const p2 = polar(a2);
    const large = a2 - a1 > 180 ? 1 : 0;
    return `M ${p1.x} ${p1.y} A ${r} ${r} 0 ${large} 1 ${p2.x} ${p2.y}`;
  };
  const trackPath = arc(startAngle, endAngle);
  const valuePath = arc(startAngle, valueAngle);
  const tickPath = arc(startAngle, thresholdAngle(threshold));

  return (
    <div className="flex flex-col items-center">
      <svg ref={ref} width={size} height={size * 0.85} viewBox={`0 0 ${size} ${size * 0.85}`}>
        {/* 背景弧 */}
        <path d={trackPath} stroke="#1e293b" strokeWidth={16} fill="none" strokeLinecap="round" />
        {/* 阈值标线 */}
        <path d={tickPath} stroke="#475569" strokeWidth={2} fill="none" strokeDasharray="2 3" />
        {/* 数值弧 */}
        <path
          d={valuePath}
          stroke={color}
          strokeWidth={16}
          fill="none"
          strokeLinecap="round"
          style={{ transition: "all 600ms ease", filter: `drop-shadow(0 0 6px ${color})` }}
        />
        {/* 中心数字 */}
        <text
          x={cx}
          y={cy + 6}
          textAnchor="middle"
          fontSize={42}
          fontWeight="700"
          fontFamily="JetBrains Mono, monospace"
          fill={color}
        >
          {value.toFixed(0)}
        </text>
        <text x={cx} y={cy + 28} textAnchor="middle" fontSize={10} fill="#94a3b8">
          EMA · 原始 {raw.toFixed(0)}
        </text>
      </svg>
      <div className="text-xs text-slate-500 mt-1">
        阈值 {threshold} · 状态 <span className="font-mono" style={{ color }}>{lifecycle}</span>
      </div>
    </div>
  );
}

function thresholdAngle(threshold: number) {
  return -135 + (threshold / 100) * 270;
}
