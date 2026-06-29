import { QueryClient } from "@tanstack/react-query";

/**
 * FE-109: 全局 QueryClient — EOD 模式优化
 *
 * Hunter Radar 后端 ETL 以 22:00 UTC 日频刷新,
 * 前端无需高频轮询。staleTime 提升至 1h,
 * 最大化缓存命中率(目标 > 80%)。
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      /** EOD 数据 staleTime 1h,切换标的时 0ms 命中缓存 */
      staleTime: 1000 * 60 * 60,
      retry: 2,
      refetchOnWindowFocus: false,
      /** 数据 6h 后 GC,释放内存 */
      gcTime: 1000 * 60 * 60 * 6,
    },
  },
});
