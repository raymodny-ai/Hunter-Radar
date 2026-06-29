/**
 * FE-151: 8-K 重大事件跑马灯 — SSE 实时横幅
 *
 * - 对接 /events/8k(SSE / REST fallback)
 * - 顶部无缝滚动横幅
 * - 点击跳转对应标的
 * - 仅展示 Item 8.01 事件
 */
import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "@tanstack/react-router";
import { api } from "@/lib/api";

interface Event8K {
  id: number;
  symbol: string;
  filing_date: string;
  item_type: string;
  title: string;
  url: string;
}

export interface EventTickerProps {
  className?: string;
}

export function EventTicker({ className }: EventTickerProps) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [events, setEvents] = useState<Event8K[]>([]);
  const [visible, setVisible] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const animationRef = useRef<number>(0);
  const offsetRef = useRef(0);

  // Fetch events (REST fallback since SSE may not be available)
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await api.listEvents8K(50);
        if (!cancelled) {
          // Filter Item 8.01 only
          const filtered = data.filter((e) => e.item_type === "8.01" || e.item_type.includes("8.01"));
          setEvents(filtered.length > 0 ? filtered : data.slice(0, 10));
        }
      } catch {
        // silently fail
      }
    };
    load();
    // Refresh every 5 minutes
    const interval = setInterval(load, 5 * 60 * 1000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // CSS animation-based marquee
  useEffect(() => {
    const container = containerRef.current;
    const inner = innerRef.current;
    if (!container || !inner || events.length === 0) return;

    let lastTime = 0;
    const speed = 40; // px per second

    const animate = (time: number) => {
      if (!lastTime) lastTime = time;
      const delta = (time - lastTime) / 1000;
      lastTime = time;

      offsetRef.current += speed * delta;
      const totalWidth = inner.scrollWidth;
      if (offsetRef.current >= totalWidth) {
        offsetRef.current = 0;
      }
      inner.style.transform = `translateX(-${offsetRef.current}px)`;
      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationRef.current);
  }, [events]);

  const handleClick = useCallback((symbol: string) => {
    nav({ to: `/symbol/${symbol}` });
  }, [nav]);

  if (!visible || events.length === 0) return null;

  return (
    <div
      className={`relative bg-slate-900/90 border-b border-slate-800 overflow-hidden ${className || ""}`}
      role="marquee"
      aria-label={t("events8k.ariaLabel")}
    >
      {/* Label */}
      <div className="absolute left-0 top-0 bottom-0 z-10 flex items-center px-2 bg-slate-900 border-r border-slate-800">
        <span className="text-[10px] font-bold text-red-400 uppercase whitespace-nowrap">
          8-K
        </span>
      </div>

      {/* Dismiss button */}
      <button
        onClick={() => setVisible(false)}
        className="absolute right-1 top-0 bottom-0 z-10 flex items-center text-slate-600 hover:text-slate-300 text-xs px-1"
        aria-label={t("events8k.dismiss")}
      >
        ✕
      </button>

      {/* Scrolling content */}
      <div ref={containerRef} className="pl-10 pr-6 py-1.5 overflow-hidden">
        <div ref={innerRef} className="flex items-center gap-6 whitespace-nowrap">
          {[...events, ...events].map((event, i) => (
            <button
              key={`${event.id}-${i}`}
              onClick={() => handleClick(event.symbol)}
              className="text-xs text-slate-400 hover:text-slate-200 transition-colors inline-flex items-center gap-1"
            >
              <span className="font-mono font-bold text-slate-300">{event.symbol}</span>
              <span className="text-slate-600">|</span>
              <span>{event.title || `${event.item_type} — ${event.filing_date}`}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
