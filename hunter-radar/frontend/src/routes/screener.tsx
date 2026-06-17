import { createRoute } from "@tanstack/react-router";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/screener",
  component: ScreenerPage,
});

function ScreenerPage() {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">每日猎物榜单</h1>
      <div className="text-slate-400 text-sm">
        BD-072 全市场 Screener 待 M2/M3 对接。当前为占位页。
      </div>
    </div>
  );
}
