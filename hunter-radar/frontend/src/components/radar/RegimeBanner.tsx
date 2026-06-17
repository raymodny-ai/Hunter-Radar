import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** 顶部市场状态横幅(BD-063 + CR-010)。*/
export function RegimeBanner() {
  const { data, isError } = useQuery({
    queryKey: ["regime"],
    queryFn: () => api.getRegime(),
    staleTime: 1000 * 60 * 30, // 30 min
    retry: 0,
  });

  if (isError || !data) return null;

  const isPanic = data.regime === "panic";
  return (
    <div
      className={`px-4 py-2 text-sm ${
        isPanic
          ? "bg-hunter-panic text-white"
          : "bg-slate-900/60 text-slate-300 border-b border-slate-800"
      }`}
    >
      <span className="font-mono">
        {isPanic ? "⚠️ PANIC" : "🟢 NORMAL"} · 红灯阈值 {data.threshold_red} · {data.banner_text}
      </span>
      {data.vix !== null && (
        <span className="ml-3 text-xs opacity-80">VIX {data.vix.toFixed(1)}</span>
      )}
    </div>
  );
}
