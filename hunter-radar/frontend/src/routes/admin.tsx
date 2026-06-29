/**
 * FE-152: Admin 管理面板 — ETL 触发 + 回测 + Webhook 重放
 *
 * - 新增路由 /admin
 * - 权限检查(非管理员显示提示)
 * - 按钮触发 /admin/etl/run / /admin/backtest/run
 */
import { useState } from "react";
import { createRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Route as RootRoute } from "./__root";
import { api, ApiError } from "../lib/api";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/admin",
  component: AdminPage,
});

function AdminPage() {
  const { t } = useTranslation();
  const [etlStatus, setEtlStatus] = useState<string | null>(null);
  const [etlLoading, setEtlLoading] = useState(false);
  const [btStatus, setBtStatus] = useState<string | null>(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btSymbol, setBtSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);

  const runETL = async () => {
    setEtlLoading(true);
    setEtlStatus(null);
    setError(null);
    try {
      const result = await api.adminRunETL();
      setEtlStatus(result.status);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError(t("admin.forbidden"));
      } else {
        setError(e instanceof ApiError ? `API ${e.status}` : String(e));
      }
    } finally {
      setEtlLoading(false);
    }
  };

  const runBacktest = async () => {
    setBtLoading(true);
    setBtStatus(null);
    setError(null);
    try {
      const body = btSymbol.trim() ? { symbol: btSymbol.trim().toUpperCase() } : undefined;
      const result = await api.adminRunBacktest(body);
      setBtStatus(result.status);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError(t("admin.forbidden"));
      } else {
        setError(e instanceof ApiError ? `API ${e.status}` : String(e));
      }
    } finally {
      setBtLoading(false);
    }
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <header>
        <h1 className="text-2xl font-bold">{t("admin.title")}</h1>
        <p className="text-sm text-slate-400 mt-1">{t("admin.subtitle")}</p>
      </header>

      {error && (
        <div className="text-red-400 text-sm bg-red-900/20 rounded p-3 border border-red-800/30">
          {error}
        </div>
      )}

      {/* ETL Section */}
      <section className="bg-slate-800/80 rounded-lg p-4 border border-slate-700/50 space-y-3">
        <h2 className="font-semibold text-base">{t("admin.etlTitle")}</h2>
        <p className="text-xs text-slate-400">{t("admin.etlDescription")}</p>
        <button
          onClick={runETL}
          disabled={etlLoading}
          className="px-4 py-2 rounded bg-hunter-red text-white text-sm disabled:opacity-50 hover:opacity-80"
        >
          {etlLoading ? t("common.loading") : t("admin.runETL")}
        </button>
        {etlStatus && (
          <div className="text-xs text-green-400">
            {t("admin.etlResult")}: {etlStatus}
          </div>
        )}
      </section>

      {/* Backtest Section */}
      <section className="bg-slate-800/80 rounded-lg p-4 border border-slate-700/50 space-y-3">
        <h2 className="font-semibold text-base">{t("admin.backtestTitle")}</h2>
        <p className="text-xs text-slate-400">{t("admin.backtestDescription")}</p>
        <div className="flex gap-2">
          <input
            value={btSymbol}
            onChange={(e) => setBtSymbol(e.target.value)}
            placeholder={t("admin.symbolPlaceholder")}
            className="flex-1 px-2 py-1 bg-slate-900 rounded text-slate-100 text-sm uppercase"
          />
          <button
            onClick={runBacktest}
            disabled={btLoading}
            className="px-4 py-2 rounded bg-hunter-red text-white text-sm disabled:opacity-50 hover:opacity-80"
          >
            {btLoading ? t("common.loading") : t("admin.runBacktest")}
          </button>
        </div>
        {btStatus && (
          <div className="text-xs text-green-400">
            {t("admin.backtestResult")}: {btStatus}
          </div>
        )}
      </section>

      <div className="text-xs text-slate-500">{t("common.disclaimer")}</div>
    </div>
  );
}
