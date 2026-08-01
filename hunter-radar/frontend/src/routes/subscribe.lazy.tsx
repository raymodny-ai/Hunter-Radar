/**
 * P3-03: Subscription 定价页 (PRD §3.7)
 *
 * - Feature comparison table (Free vs Pro, 7 行)
 * - "Upgrade" → Stripe Checkout (redirect)
 * - Success/failure callback (?status=success|failure)
 * - Current plan indicator + usage meter (useApiQuota)
 */
import { useState } from "react";
import { createLazyRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../lib/api";
import { useApiQuota } from "@/features/useApiQuota";
import { toast } from "@/components/common/Toast";

// ── Route (with ?status=success|failure callback) ──

type SubscribeSearch = { status?: "success" | "failure" };

export const Route = createLazyRoute("/subscribe")({
  component: SubscribePage,
});

// ── Comparison table spec (PRD §3.7) ──────────────

type ComparisonRow = {
  key: string;
  free: string;
  pro: string;
};

const COMPARISON_ROWS: ComparisonRow[] = [
  { key: "threatHistory", free: "threatHistoryFree", pro: "threatHistoryPro" },
  { key: "screener", free: "screenerFree", pro: "screenerPro" },
  { key: "llm", free: "llmFree", pro: "llmPro" },
  { key: "webPush", free: "webPushFree", pro: "webPushPro" },
  { key: "basketMembers", free: "basketMembersFree", pro: "basketMembersPro" },
  { key: "apiQuota", free: "apiQuotaFree", pro: "apiQuotaPro" },
  { key: "backtest", free: "backtestFree", pro: "backtestPro" },
];

// ── Main Page ─────────────────────────────────────

function SubscribePage() {
  const { t } = useTranslation();
  const status = Route.useSearch().status;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <header className="text-center">
        <h1 className="text-2xl font-bold">{t("subscribe.title")}</h1>
        <p className="text-slate-400 text-sm mt-2">{t("subscribe.subtitle")}</p>
      </header>

      {/* Checkout callback banners */}
      {status === "success" && (
        <div
          role="status"
          className="rounded-md border border-emerald-700/60 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-300"
        >
          ✓ {t("subscribe.successBanner")}
        </div>
      )}
      {status === "failure" && (
        <div
          role="alert"
          className="rounded-md border border-red-700/60 bg-red-950/40 px-4 py-3 text-sm text-red-300"
        >
          ✗ {t("subscribe.failureBanner")}
        </div>
      )}

      {/* Current plan + usage meter */}
      <CurrentPlanCard />

      {/* Feature comparison table */}
      <ComparisonTable />

      {/* Pricing cards */}
      <PricingCards />

      <div className="text-xs text-slate-500 text-center">{t("common.disclaimer")}</div>
    </div>
  );
}

// ── Current Plan + Usage Meter ────────────────────

function CurrentPlanCard() {
  const { t } = useTranslation();
  const quota = useApiQuota();

  const sub = useQuery({
    queryKey: ["subscription"],
    queryFn: async () => {
      try {
        return await api.getSubscription();
      } catch (e) {
        if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
          return null; // sandbox: billing not deployed
        }
        throw e;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });

  const tier = sub.data?.tier ?? quota.data?.tier ?? "pro";
  const isPro = tier === "pro";
  const isSandbox = quota.data?.is_sandbox ?? true;

  const used = quota.data?.used ?? 0;
  const limit = quota.data?.limit ?? -1;
  const unlimited = limit < 0;
  const pct = unlimited ? 0 : Math.min(100, (used / limit) * 100);

  return (
    <section
      aria-label={t("subscribe.currentPlan")}
      className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3"
    >
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm font-semibold text-slate-300">{t("subscribe.currentPlan")}</h2>
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${
            isPro ? "bg-red-900/50 text-red-300 border border-red-700/50" : "bg-slate-700/60 text-slate-300"
          }`}
        >
          {isPro ? "PRO" : "FREE"}
        </span>
      </div>

      {sub.data?.status === "cancel_pending" && (
        <div className="text-xs text-amber-400">{t("subscribe.cancelPending")}</div>
      )}

      {/* Usage meter */}
      <div>
        <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
          <span>{t("subscribe.usage.apiCalls")}</span>
          <span className="font-mono">
            {unlimited
              ? t("subscribe.usage.unlimited")
              : `${used} / ${limit}`}
          </span>
        </div>
        <div
          className="h-2 bg-slate-700 rounded-full overflow-hidden"
          role="meter"
          aria-label={t("subscribe.usage.apiCalls")}
          aria-valuenow={unlimited ? undefined : used}
          aria-valuemin={0}
          aria-valuemax={unlimited ? undefined : limit}
        >
          <div
            className={`h-full rounded-full transition-all ${
              pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-400" : "bg-emerald-500"
            }`}
            style={{ width: unlimited ? "100%" : `${pct}%` }}
          />
        </div>
      </div>

      {isSandbox && (
        <div className="text-[11px] text-slate-500 bg-slate-900/60 rounded px-2 py-1.5">
          ⓘ {t("subscribe.sandboxNote")}
        </div>
      )}
    </section>
  );
}

// ── Feature Comparison Table (PRD §3.7) ───────────

function ComparisonTable() {
  const { t } = useTranslation();

  return (
    <section aria-label={t("subscribe.comparison.title")}>
      <h2 className="text-lg font-semibold mb-3">{t("subscribe.comparison.title")}</h2>
      <div className="overflow-x-auto rounded-lg border border-slate-700/50">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-800/80 text-left">
              <th className="px-4 py-3 font-medium text-slate-300">
                {t("subscribe.comparison.feature")}
              </th>
              <th className="px-4 py-3 font-medium text-slate-400">
                {t("subscribe.comparison.free")}
              </th>
              <th className="px-4 py-3 font-medium text-red-400">
                {t("subscribe.comparison.pro")}
              </th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON_ROWS.map((row, i) => (
              <tr
                key={row.key}
                className={`border-t border-slate-800/60 ${i % 2 === 1 ? "bg-slate-900/40" : ""}`}
              >
                <td className="px-4 py-2.5 text-slate-300">
                  {t(`subscribe.comparison.${row.key}`)}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-400">
                  {t(`subscribe.comparison.${row.free}`)}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-200">
                  {t(`subscribe.comparison.${row.pro}`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Pricing Cards + Checkout ──────────────────────

function PricingCards() {
  const { t } = useTranslation();
  const [checkingOut, setCheckingOut] = useState<string | null>(null);

  const startCheckout = async (plan: "pro_monthly" | "pro_yearly") => {
    setCheckingOut(plan);
    try {
      const session = await api.createCheckoutSession(plan);
      // Stripe Checkout redirect
      window.location.href = session.checkout_url;
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
        toast.info(t("subscribe.sandboxNote"));
      } else {
        toast.error(t("subscribe.checkoutUnavailable"));
      }
    } finally {
      setCheckingOut(null);
    }
  };

  return (
    <section aria-label={t("subscribe.priceGrid")}>
      <h2 className="text-lg font-semibold mb-3">{t("subscribe.priceGrid")}</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Free */}
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-5 flex flex-col gap-3">
          <h3 className="font-semibold text-slate-200">{t("subscribe.free.title")}</h3>
          <div className="text-2xl font-bold font-mono text-slate-100">
            $0
            <span className="text-xs font-normal text-slate-500"> / {t("subscribe.free.period")}</span>
          </div>
          <ul className="text-xs text-slate-400 space-y-1.5 flex-1">
            <li>· {t("subscribe.free.feature1")}</li>
            <li>· {t("subscribe.free.feature2")}</li>
            <li>· {t("subscribe.free.feature3")}</li>
          </ul>
          <button
            disabled
            className="px-3 py-2 rounded bg-slate-700/50 text-slate-500 text-sm cursor-not-allowed"
          >
            {t("subscribe.free.cta")}
          </button>
        </div>

        {/* Pro Monthly */}
        <div className="rounded-lg border border-red-700/50 bg-slate-800/60 p-5 flex flex-col gap-3 relative">
          <span className="absolute -top-2.5 left-4 px-2 py-0.5 rounded-full bg-hunter-red text-white text-[10px] font-bold">
            PRO
          </span>
          <h3 className="font-semibold text-slate-100">{t("subscribe.proMonthlyTitle")}</h3>
          <div className="text-2xl font-bold font-mono text-slate-100">
            $29
            <span className="text-xs font-normal text-slate-500"> {t("subscribe.perMonth")}</span>
          </div>
          <ul className="text-xs text-slate-400 space-y-1.5 flex-1">
            <li>· {t("subscribe.proMonthly.feature1")}</li>
            <li>· {t("subscribe.proMonthly.feature2")}</li>
            <li>· {t("subscribe.proMonthly.feature3")}</li>
          </ul>
          <button
            onClick={() => startCheckout("pro_monthly")}
            disabled={checkingOut !== null}
            className="px-3 py-2 rounded bg-hunter-red text-white text-sm font-medium hover:opacity-85 transition-opacity disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-red-400"
          >
            {checkingOut === "pro_monthly" ? t("common.loading") : t("subscribe.cta")}
          </button>
        </div>

        {/* Pro Yearly */}
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-5 flex flex-col gap-3 relative">
          <span className="absolute -top-2.5 left-4 px-2 py-0.5 rounded-full bg-emerald-600 text-white text-[10px] font-bold">
            {t("subscribe.saveBadge")} 17%
          </span>
          <h3 className="font-semibold text-slate-100">{t("subscribe.proYearlyTitle")}</h3>
          <div className="text-2xl font-bold font-mono text-slate-100">
            $290
            <span className="text-xs font-normal text-slate-500"> {t("subscribe.perYear")}</span>
          </div>
          <ul className="text-xs text-slate-400 space-y-1.5 flex-1">
            <li>· {t("subscribe.proYearly.feature1")}</li>
            <li>· {t("subscribe.proYearly.feature2")}</li>
            <li>· {t("subscribe.proYearly.feature3")}</li>
          </ul>
          <button
            onClick={() => startCheckout("pro_yearly")}
            disabled={checkingOut !== null}
            className="px-3 py-2 rounded bg-slate-700 text-slate-100 text-sm font-medium hover:bg-slate-600 transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-slate-400"
          >
            {checkingOut === "pro_yearly" ? t("common.loading") : t("subscribe.cta")}
          </button>
        </div>
      </div>
    </section>
  );
}
