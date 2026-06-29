/**
 * FE-116: useLookup Hook — 搜索防抖 + React Query 缓存
 *
 * PRD §2.1: 全局搜索框
 * - 300ms debounce
 * - queryKey ['lookup', q]
 * - staleTime 10min
 * - 返回 { ticker, name, type, exchange }[]
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState, useEffect, useRef } from "react";

export interface LookupResult {
  ticker: string;
  name: string;
  type: string;
  exchange: string;
}

interface UseLookupReturn {
  /** 当前输入值(实时) */
  query: string;
  /** 更新输入值 */
  setQuery: (q: string) => void;
  /** 防抖后的查询结果 */
  results: LookupResult[];
  /** 是否正在请求 */
  isLoading: boolean;
  /** 请求错误 */
  isError: boolean;
  /** 是否有结果 */
  hasResults: boolean;
}

export function useLookup(): UseLookupReturn {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  // 300ms 防抖
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebounced(query);
    }, 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query]);

  const trimmed = debounced.trim();
  const shouldFetch = trimmed.length >= 1;

  const { data, isLoading, isError } = useQuery<LookupResult[]>({
    queryKey: ["lookup", trimmed],
    queryFn: () => api.lookup(trimmed),
    enabled: shouldFetch,
    staleTime: 1000 * 60 * 10, // 10min
    retry: 0,
  });

  return {
    query,
    setQuery,
    results: data ?? [],
    isLoading: shouldFetch && isLoading,
    isError: !!isError,
    hasResults: (data?.length ?? 0) > 0,
  };
}
