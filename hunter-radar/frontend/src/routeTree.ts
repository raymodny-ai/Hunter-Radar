// 手动路由树（替代 @tanstack/router-vite-plugin 自动生成）
// 参见 frontend-plan.md §4.2 Router 拓扑
import { Route as rootRoute } from "./routes/__root";
import { Route as indexRoute } from "./routes/index";
import { Route as screenerRoute } from "./routes/screener";
import { Route as symbolRoute } from "./routes/symbol.$ticker";
import { Route as alertsRoute } from "./routes/alerts";
import { Route as basketRoute } from "./routes/basket";
import { Route as regimeRoute } from "./routes/regime";
import { Route as adminRoute } from "./routes/admin";
import { Route as logsRoute } from "./routes/logs";
import { createRouter } from "@tanstack/react-router";

// 构建路由树
const routeTree = rootRoute.addChildren([
  indexRoute,
  screenerRoute,
  symbolRoute,
  alertsRoute,
  basketRoute,
  regimeRoute,
  adminRoute,
  logsRoute,
]);

export const router = createRouter({ routeTree });

export { routeTree };
