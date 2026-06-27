import { createRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/subscribe",
  component: SubscribeRedirect,
});

function SubscribeRedirect() {
  const nav = useNavigate();
  useEffect(() => {
    nav({ to: "/" });
  }, [nav]);
  return null;
}
