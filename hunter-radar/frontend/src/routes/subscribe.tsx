import { createRoute, useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type PlanDTO } from "@/lib/api";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/subscribe",
  component: SubscribePage,
});

function SubscribePage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const qc = useQueryClient();

  const plans = useQuery({
    queryKey: ["subscriptions", "plans"],
    queryFn: () => api.getPlans(),
    retry: 0,
  });

  const me = useQuery({
    queryKey: ["subscriptions", "me"],
    queryFn: () => api.getMySubscription(),
    retry: 0,
  });

  const checkoutMut = useMutation({
    mutationFn: (plan: "pro_monthly" | "pro_yearly") => api.postCheckout(plan),
    onSuccess: async (session) => {
      // 沙箱:checkout_url 直接是 backend sandbox-complete 端点
      // 生产:跳转到 Stripe Checkout hosted page
      if (session.sandbox) {
        await fetch(session.checkout_url, { credentials: "include" });
        await qc.invalidateQueries({ queryKey: ["subscriptions", "me"] });
        nav({ to: "/subscribe" });
      } else {
        window.location.href = session.checkout_url;
      }
    },
  });

  const cancelMut = useMutation({
    mutationFn: () => api.postCancelSubscription(true),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["subscriptions", "me"] });
    },
  });

  const isActivePro =
    me.data?.status === "active" && me.data?.tier === "pro";

  return (
    <div className="space-y-6 max-w-5xl">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          {t("subscribe.title")}
        </h1>
        <p className="text-slate-400 text-sm">{t("subscribe.subtitle")}</p>
      </header>

      {/* 当前订阅状态 */}
      <section
        aria-label={t("subscribe.currentPlan")}
        className="rounded-md border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm flex flex-wrap items-center gap-3"
      >
        <span className="text-slate-400">{t("subscribe.currentPlan")}:</span>
        {isActivePro ? (
          <>
            <span className="px-2 py-0.5 rounded bg-emerald-700/30 text-emerald-300 font-mono text-xs">
              PRO · {me.data?.plan}
            </span>
            {me.data?.cancel_at_period_end && (
              <span className="text-amber-400 text-xs">
                {t("subscribe.cancelPending")}
              </span>
            )}
            <button
              type="button"
              onClick={() => cancelMut.mutate()}
              disabled={cancelMut.isPending || me.data?.cancel_at_period_end}
              className="ml-auto text-xs text-slate-400 hover:text-rose-400 underline disabled:opacity-50"
            >
              {cancelMut.isPending
                ? t("common.loading")
                : t("subscribe.cancelBtn")}
            </button>
          </>
        ) : (
          <span className="px-2 py-0.5 rounded bg-slate-700/40 text-slate-300 font-mono text-xs">
            FREE
          </span>
        )}
      </section>

      {/* 价格档卡片 */}
      <section
        aria-label={t("subscribe.priceGrid")}
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        {/* Free 档 */}
        <PlanCard
          tier="free"
          title={t("subscribe.free.title")}
          price="$0"
          period={t("subscribe.free.period")}
          features={[
            t("subscribe.free.feature1"),
            t("subscribe.free.feature2"),
            t("subscribe.free.feature3"),
          ]}
          current={me.data?.tier === "free"}
          ctaLabel={t("subscribe.free.cta")}
          disabled
        />

        {/* Pro 月付 + 年付 从后端拉 */}
        {plans.isLoading && (
          <div className="col-span-2 text-slate-500 text-sm">
            {t("common.loading")}
          </div>
        )}
        {plans.data?.plans.map((p: PlanDTO) => (
          <PlanCard
            key={p.id}
            tier={p.id === "pro_monthly" ? "pro_monthly" : "pro_yearly"}
            title={p.name}
            price={`$${p.price_usd}`}
            period={
              p.id === "pro_monthly"
                ? t("subscribe.proMonthly.period")
                : t("subscribe.proYearly.period")
            }
            badge={
              p.id === "pro_yearly" && p.savings_usd > 0
                ? `${t("subscribe.saveBadge")} $${p.savings_usd}`
                : undefined
            }
            features={
              p.id === "pro_monthly"
                ? [
                    t("subscribe.proMonthly.feature1"),
                    t("subscribe.proMonthly.feature2"),
                    t("subscribe.proMonthly.feature3"),
                  ]
                : [
                    t("subscribe.proYearly.feature1"),
                    t("subscribe.proYearly.feature2"),
                    t("subscribe.proYearly.feature3"),
                  ]
            }
            current={isActivePro && me.data?.plan === p.id}
            ctaLabel={
              isActivePro && me.data?.plan === p.id
                ? t("subscribe.currentBtn")
                : t("subscribe.cta")
            }
            disabled={
              checkoutMut.isPending ||
              (isActivePro && me.data?.plan === p.id)
            }
            onCta={() => checkoutMut.mutate(p.id)}
          />
        ))}
      </section>

      {/* 错误信息 */}
      {(checkoutMut.isError || cancelMut.isError) && (
        <div className="text-rose-400 text-xs" role="alert">
          {t("subscribe.error")}
        </div>
      )}

      {/* 合规兜底 */}
      <p className="text-xs text-slate-500 leading-relaxed border-t border-slate-800 pt-4">
        {t("common.disclaimer")}
      </p>
    </div>
  );
}

interface PlanCardProps {
  tier: "free" | "pro_monthly" | "pro_yearly";
  title: string;
  price: string;
  period: string;
  features: string[];
  current?: boolean;
  badge?: string;
  ctaLabel: string;
  disabled?: boolean;
  onCta?: () => void;
}

function PlanCard({
  title,
  price,
  period,
  features,
  current,
  badge,
  ctaLabel,
  disabled,
  onCta,
}: PlanCardProps) {
  return (
    <article
      className={[
        "rounded-lg border p-5 flex flex-col gap-4 transition-colors",
        current
          ? "border-emerald-600 bg-emerald-950/20"
          : "border-slate-800 bg-slate-900/40 hover:border-slate-600",
      ].join(" ")}
    >
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-lg">{title}</h3>
          {badge && (
            <span className="px-2 py-0.5 rounded bg-amber-700/30 text-amber-300 text-xs font-mono">
              {badge}
            </span>
          )}
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold">{price}</span>
          <span className="text-slate-500 text-sm">/ {period}</span>
        </div>
      </div>
      <ul className="space-y-1 text-sm text-slate-300 flex-1">
        {features.map((f) => (
          <li key={f} className="flex gap-2">
            <span className="text-emerald-400" aria-hidden="true">
              ✓
            </span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onCta}
        disabled={disabled}
        className={[
          "w-full py-2 rounded-md font-medium transition-colors",
          current
            ? "bg-emerald-700/40 text-emerald-200 cursor-default"
            : "bg-sky-600 hover:bg-sky-500 text-white disabled:opacity-50",
        ].join(" ")}
      >
        {ctaLabel}
      </button>
    </article>
  );
}