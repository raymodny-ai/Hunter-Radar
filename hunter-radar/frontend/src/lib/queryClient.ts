import { QueryClient } from "@tanstack/react-query";

/** 全局 QueryClient:staleTime 5min,失败重试 2 次。 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});
