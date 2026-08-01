/**
 * Route stub — 实现见 subscribe.lazy.tsx (PRD §7.1 路由级代码分割)
 * validateSearch 保留在 stub(搜索参数解析需同步可用)。
 */
import { createRoute } from "@tanstack/react-router";
import { Route as RootRoute } from "./__root";

type SubscribeSearch = { status?: "success" | "failure" };

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/subscribe",
  validateSearch: (search: Record<string, unknown>): SubscribeSearch => ({
    status:
      search.status === "success" || search.status === "failure"
        ? search.status
        : undefined,
  }),
}).lazy(() => import("./subscribe.lazy").then((d) => d.Route));
