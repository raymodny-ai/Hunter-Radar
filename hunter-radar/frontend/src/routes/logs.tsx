/**
 * Route stub — 实现见 logs.lazy.tsx (PRD §7.1 路由级代码分割)
 */
import { createRoute } from "@tanstack/react-router";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/logs",
}).lazy(() => import("./logs.lazy").then((d) => d.Route));
