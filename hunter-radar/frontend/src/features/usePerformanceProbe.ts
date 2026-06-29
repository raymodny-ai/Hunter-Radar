/**
 * FE-153: usePerformanceProbe — 前端性能探针上报
 *
 * 采集 FCP / LCP / Widget 曝光时长:
 * - batch POST 到 /analytics/events
 * - 5s 防抖
 * - 使用 PerformanceObserver API
 */
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";

interface PerformanceEvent {
  event: string;
  value?: number;
  meta?: Record<string, unknown>;
}

let pendingEvents: PerformanceEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleFlush() {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    if (pendingEvents.length === 0) return;
    const events = [...pendingEvents];
    pendingEvents = [];
    api.reportAnalytics(events).catch(() => {
      // silently fail
    });
  }, 5000);
}

function enqueue(event: PerformanceEvent) {
  pendingEvents.push(event);
  scheduleFlush();
}

export function usePerformanceProbe() {
  const observed = useRef(false);

  useEffect(() => {
    if (observed.current) return;
    if (typeof PerformanceObserver === "undefined") return;
    observed.current = true;

    // FCP (First Contentful Paint)
    try {
      const fcpObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === "first-contentful-paint") {
            enqueue({ event: "FCP", value: entry.startTime });
          }
        }
      });
      fcpObserver.observe({ type: "paint", buffered: true });
    } catch {
      // paint observer may not be available
    }

    // LCP (Largest Contentful Paint)
    try {
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        if (entries.length > 0) {
          const last = entries[entries.length - 1];
          enqueue({ event: "LCP", value: last.startTime });
        }
      });
      lcpObserver.observe({ type: "largest-contentful-paint", buffered: true });
    } catch {
      // LCP may not be available
    }

    // CLS (Cumulative Layout Shift)
    try {
      let clsValue = 0;
      const clsObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!(entry as unknown as { hadRecentInput: boolean }).hadRecentInput) {
            clsValue += (entry as unknown as { value: number }).value;
          }
        }
        enqueue({ event: "CLS", value: clsValue });
      });
      clsObserver.observe({ type: "layout-shift", buffered: true });
    } catch {
      // CLS may not be available
    }

    // Report page load time after load event
    const reportLoad = () => {
      setTimeout(() => {
        if (performance.getEntriesByType) {
          const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
          if (nav) {
            enqueue({
              event: "page_load",
              value: nav.loadEventEnd - nav.startTime,
              meta: {
                domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
                responseEnd: nav.responseEnd - nav.startTime,
              },
            });
          }
        }
      }, 1000);
    };

    if (document.readyState === "complete") {
      reportLoad();
    } else {
      window.addEventListener("load", reportLoad, { once: true });
    }
  }, []);
}

/**
 * Report a widget exposure event.
 */
export function reportWidgetExposure(widgetName: string, durationMs?: number) {
  enqueue({
    event: "widget_exposure",
    value: durationMs,
    meta: { widget: widgetName },
  });
}
