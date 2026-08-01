/**
 * P1-01: 7 日 Sparkline 迷你趋势线 (Dashboard 排名列表用)
 *
 * - 纯 SVG polyline,无 ECharts 依赖(20 行列表性能优先)
 * - 数据源: /symbols/{ticker}/threat-history?days=7 (TanStack Query 缓存 1h)
 * - 色彩跟随最新分数色阶 (PRD Appendix A)
 * - aria-hidden (装饰性,排名行本身有分数 aria-label)
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { threatScoreColor } from "@/lib/design-tokens";

interface SparklineProps {
  ticker: string;
  width?: number;
  height?: number;
  className?: string;
}

export function Sparkline({ ticker, width = 64, height = 20, className }: SparklineProps) {
  const { data } = useQuery({
    queryKey: ["symbols", ticker, "threat-history", 7],
    queryFn: () => api.getThreatHistory(ticker, 7),
    staleTime: 1000 * 60 * 60, // EOD 数据 1h 缓存
    retry: 0,
  });

  if (!data || data.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        className={className}
        aria-hidden="true"
      >
        <line
          x1={2}
          y1={height / 2}
          x2={width - 2}
          y2={height / 2}
          stroke="#334155"
          strokeWidth={1}
          strokeDasharray="2 2"
        />
      </svg>
    );
  }

  const values = data.map((d) => d.total);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values
    .map((v, i) => {
      const x = 2 + (i / (values.length - 1)) * (width - 4);
      const y = height - 3 - ((v - min) / range) * (height - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const lastValue = values[values.length - 1];
  const color = threatScoreColor(lastValue);

  return (
    <svg width={width} height={height} className={className} aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.85}
      />
    </svg>
  );
}
