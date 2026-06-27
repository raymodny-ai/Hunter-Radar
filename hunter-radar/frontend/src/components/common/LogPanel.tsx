import { useEffect, useRef, useState } from "react";

interface LogEntry {
  ts: string;
  level: string;
  msg: string;
  extra?: Record<string, unknown>;
}

const LEVEL_COLORS: Record<string, string> = {
  INFO: "text-sky-300",
  WARNING: "text-amber-300",
  ERROR: "text-red-300",
  CRITICAL: "text-red-400 font-bold",
  DEBUG: "text-slate-500",
};

const LEVEL_BG: Record<string, string> = {
  INFO: "bg-sky-950/20",
  WARNING: "bg-amber-950/20",
  ERROR: "bg-red-950/20",
  CRITICAL: "bg-red-950/40",
  DEBUG: "bg-transparent",
};

export function LogPanel({ visible }: { visible: boolean }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterLevel, setFilterLevel] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible) return;

    // 先拉历史日志
    fetch("/api/v1/logs/history?limit=200")
      .then((r) => r.json())
      .then((data) => setLogs(data))
      .catch(() => {});

    // SSE 连接
    const es = new EventSource("/api/v1/logs/stream");
    es.onmessage = (e) => {
      try {
        const entry: LogEntry = JSON.parse(e.data);
        setLogs((prev) => {
          const next = [...prev, entry];
          // 最多保留 1000 条
          return next.length > 1000 ? next.slice(-500) : next;
        });
      } catch {
        // ignore heartbeats and parse errors
      }
    };
    es.onerror = () => {
      // SSE 连接断开,10s 后自动重连(EventSource 默认行为)
    };

    return () => {
      es.close();
    };
  }, [visible]);

  // 自动滚到底部
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filtered = filterLevel
    ? logs.filter((l) => l.level === filterLevel)
    : logs;

  const levelCounts = logs.reduce(
    (acc, l) => {
      acc[l.level] = (acc[l.level] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 right-0 w-full md:w-2/3 lg:w-1/2 h-80 bg-slate-950 border-t border-l border-slate-800 shadow-2xl z-50 flex flex-col">
      {/* 工具栏 */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 border-b border-slate-800 text-xs text-slate-400">
        <span className="font-mono font-bold text-slate-300">📋 Logs</span>

        {/* 级别过滤 */}
        <div className="flex gap-1 ml-2">
          {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((level) => {
            const count = levelCounts[level] || 0;
            const active = filterLevel === level;
            return (
              <button
                key={level}
                onClick={() => setFilterLevel(active ? null : level)}
                className={`px-1.5 py-0.5 rounded font-mono ${
                  active ? "bg-slate-700 text-slate-100" : "text-slate-500 hover:text-slate-300"
                }`}
                title={`${level}: ${count}`}
              >
                {level[0]}
                {count > 0 && (
                  <span className="ml-0.5 text-[10px] opacity-60">{count}</span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex-1" />

        {/* 自动滚动开关 */}
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={() => setAutoScroll(!autoScroll)}
            className="accent-slate-400"
          />
          滚动
        </label>

        {/* 清空 */}
        <button
          onClick={() => setLogs([])}
          className="px-1.5 py-0.5 rounded hover:bg-slate-800 hover:text-slate-200"
        >
          🗑
        </button>
      </div>

      {/* 日志列表 */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed px-2 py-1 space-y-0.5"
        style={{ fontFamily: "JetBrains Mono, Menlo, monospace" }}
      >
        {filtered.length === 0 && (
          <div className="text-slate-600 text-center py-8">
            {logs.length === 0 ? "连接中…" : "无匹配日志"}
          </div>
        )}
        {filtered.map((entry, i) => {
          const time = entry.ts?.slice(11, 23) || "--:--:--";
          const color = LEVEL_COLORS[entry.level] || "text-slate-300";
          const bg = LEVEL_BG[entry.level] || "";
          const extraStr = entry.extra
            ? " " + JSON.stringify(entry.extra).slice(0, 120)
            : "";

          return (
            <div key={i} className={`${bg} rounded px-1`}>
              <span className="text-slate-600 mr-1">{time}</span>
              <span className={`${color} mr-1 w-12 inline-block`}>
                {entry.level.padEnd(5)}
              </span>
              <span className="text-slate-200">{entry.msg}</span>
              {extraStr && (
                <span className="text-slate-500 text-[10px]">{extraStr}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
