import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import "./index.css";
import "./i18n";
import { queryClient } from "./lib/queryClient";
import { initSentry } from "./lib/sentry";
import { router } from "./router";

// m5t7 FE-069:Sentry 初始化必须在 ReactDOM.render 之前(Vite 静态导入顺序)
initSentry();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
