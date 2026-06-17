import { useEffect, useState } from "react";
import { createRoute } from "@tanstack/react-router";
import { Route as RootRoute } from "./__root";
import {
  api,
  ApiError,
  BasketDTO,
  BasketMemberDTO,
  BasketDistributionDTO,
} from "../lib/api";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/basket",
  component: BasketPage,
});

type View = { kind: "list" } | { kind: "create" } | { kind: "detail"; basketId: number };

function BasketPage() {
  const [view, setView] = useState<View>({ kind: "list" });
  const [baskets, setBaskets] = useState<BasketDTO[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listBaskets();
      setBaskets(data);
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (view.kind === "list") {
      refresh();
    }
  }, [view.kind]);

  if (view.kind === "list") {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">自选篮子</h1>
          <button
            onClick={() => setView({ kind: "create" })}
            className="px-3 py-1 rounded bg-hunter-red text-white text-sm hover:opacity-80"
          >
            + 新建篮子
          </button>
        </div>
        {error && <div className="text-red-400 text-sm">加载失败：{error}</div>}
        {loading && <div className="text-slate-400 text-sm">加载中…</div>}
        {!loading && baskets.length === 0 && (
          <div className="text-slate-400 text-sm">还没有篮子，点击右上角新建。</div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {baskets.map((b) => (
            <div
              key={b.id}
              className="bg-slate-800 rounded p-3 cursor-pointer hover:bg-slate-700"
              onClick={() => setView({ kind: "detail", basketId: b.id })}
            >
              <div className="font-semibold">{b.name}</div>
              {b.description && (
                <div className="text-xs text-slate-400 mt-1">{b.description}</div>
              )}
              <div className="text-xs text-slate-500 mt-2">
                {b.member_count} 个标的 · 更新于 {b.updated_at}
              </div>
            </div>
          ))}
        </div>
        <div className="text-xs text-slate-500">
          数据来源：FINRA + SEC EDGAR + Yahoo Finance。统计异常现象，仅供参考，不构成投资建议。
        </div>
      </div>
    );
  }

  if (view.kind === "create") {
    return (
      <CreateBasketView
        onCancel={() => setView({ kind: "list" })}
        onCreated={async (b) => {
          await refresh();
          setView({ kind: "detail", basketId: b.id });
        }}
      />
    );
  }

  return (
    <BasketDetailView
      basketId={view.basketId}
      onBack={() => {
        refresh();
        setView({ kind: "list" });
      }}
    />
  );
}

function CreateBasketView({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (b: BasketDTO) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) {
      setError("请输入篮子名称");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const b = await api.createBasket({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      onCreated(b);
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-3 max-w-md">
      <h1 className="text-2xl font-bold">新建篮子</h1>
      <label className="block">
        <span className="text-sm text-slate-300">名称（必填）</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={80}
          className="mt-1 w-full px-2 py-1 bg-slate-800 rounded text-slate-100"
          placeholder="如：科技龙头"
        />
      </label>
      <label className="block">
        <span className="text-sm text-slate-300">描述（可选）</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
          className="mt-1 w-full px-2 py-1 bg-slate-800 rounded text-slate-100"
          rows={3}
        />
      </label>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={submitting}
          className="px-3 py-1 rounded bg-hunter-red text-white text-sm disabled:opacity-50"
        >
          {submitting ? "创建中…" : "创建"}
        </button>
        <button
          onClick={onCancel}
          className="px-3 py-1 rounded bg-slate-700 text-slate-100 text-sm"
        >
          取消
        </button>
      </div>
    </div>
  );
}

function BasketDetailView({
  basketId,
  onBack,
}: {
  basketId: number;
  onBack: () => void;
}) {
  const [basket, setBasket] = useState<BasketDTO | null>(null);
  const [members, setMembers] = useState<BasketMemberDTO[]>([]);
  const [distribution, setDistribution] = useState<BasketDistributionDTO | null>(null);
  const [newTickers, setNewTickers] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, ms, dist] = await Promise.all([
        api.getBasket(basketId),
        api.listBasketMembers(basketId),
        api.getBasketDistribution(basketId, 30).catch(() => null),
      ]);
      setBasket(b);
      setMembers(ms);
      setDistribution(dist);
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, [basketId]);

  const addMembers = async () => {
    const tickers = newTickers
      .split(/[\s,]+/)
      .map((s) => s.trim().toUpperCase())
      .filter((s) => s.length > 0);
    if (tickers.length === 0) return;
    setError(null);
    try {
      const r = await api.addBasketMembers(basketId, tickers);
      setNewTickers("");
      await refresh();
      if (r.inserted < tickers.length) {
        setError(`已添加 ${r.inserted}/${r.submitted} 个，其余可能重复或不存在`);
      }
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  const removeMember = async (ticker: string) => {
    try {
      await api.removeBasketMember(basketId, ticker);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  const deleteBasket = async () => {
    if (!confirm("确定删除该篮子？")) return;
    try {
      await api.deleteBasket(basketId);
      onBack();
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  if (loading && !basket) {
    return <div className="text-slate-400">加载中…</div>;
  }
  if (!basket) {
    return <div className="text-red-400 text-sm">篮子不存在</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={onBack}
            className="text-sm text-slate-400 hover:text-slate-200"
          >
            ← 返回列表
          </button>
          <h1 className="text-2xl font-bold mt-1">{basket.name}</h1>
          {basket.description && (
            <div className="text-sm text-slate-400 mt-1">{basket.description}</div>
          )}
        </div>
        <button
          onClick={deleteBasket}
          className="px-2 py-1 text-xs rounded bg-slate-700 text-red-300 hover:bg-slate-600"
        >
          删除篮子
        </button>
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      <section>
        <h2 className="text-lg font-semibold mb-2">成员（{members.length}）</h2>
        <div className="flex gap-2 mb-2">
          <input
            value={newTickers}
            onChange={(e) => setNewTickers(e.target.value)}
            placeholder="AAPL, TSLA, MSFT"
            className="flex-1 px-2 py-1 bg-slate-800 rounded text-slate-100 text-sm"
          />
          <button
            onClick={addMembers}
            className="px-3 py-1 rounded bg-hunter-red text-white text-sm"
          >
            + 添加
          </button>
        </div>
        {members.length === 0 ? (
          <div className="text-slate-400 text-sm">
            还没有成员。输入 ticker 批量添加（逗号或空格分隔）。
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {members.map((m) => (
              <div
                key={m.ticker}
                className="bg-slate-800 rounded px-2 py-1 text-sm flex items-center justify-between"
              >
                <span className="font-mono">{m.ticker}</span>
                <button
                  onClick={() => removeMember(m.ticker)}
                  className="text-xs text-slate-500 hover:text-red-400"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-2">分布（近 30 日）</h2>
        {!distribution ? (
          <div className="text-slate-400 text-sm">
            暂无分布数据（空篮子或无 threat_score_daily 数据）。
          </div>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-3 md:grid-cols-5 gap-2 text-sm">
              <Stat label="均值" v={distribution.mean} />
              <Stat label="p25" v={distribution.p25} />
              <Stat label="p50" v={distribution.p50} />
              <Stat label="p75" v={distribution.p75} />
              <Stat label="p90" v={distribution.p90} />
              <Stat label="p99" v={distribution.p99} />
              <Stat label="最小" v={distribution.min_score} />
              <Stat label="最大" v={distribution.max_score} />
              <Stat label="标的数" v={distribution.ticker_count} />
              <Stat label="平均日" v={distribution.day_count} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-300 mb-1">
                逐 ticker
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-400 text-left">
                    <th className="py-1">ticker</th>
                    <th>latest</th>
                    <th>mean</th>
                    <th>max</th>
                    <th>lifecycle</th>
                  </tr>
                </thead>
                <tbody>
                  {distribution.by_ticker.map((r) => (
                    <tr key={r.ticker} className="border-t border-slate-800">
                      <td className="py-1 font-mono">{r.ticker}</td>
                      <td>{r.latest ?? "—"}</td>
                      <td>{r.mean}</td>
                      <td>{r.max}</td>
                      <td>
                        <span
                          className={
                            r.lifecycle === "red"
                              ? "text-hunter-red"
                              : r.lifecycle === "yellow"
                              ? "text-hunter-yellow"
                              : r.lifecycle === "green"
                              ? "text-hunter-green"
                              : "text-slate-400"
                          }
                        >
                          {r.lifecycle}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <div className="text-xs text-slate-500">
        数据来源：FINRA + SEC EDGAR + Yahoo Finance。统计异常现象，仅供参考，不构成投资建议。
      </div>
    </div>
  );
}

function Stat({ label, v }: { label: string; v: number }) {
  return (
    <div className="bg-slate-800 rounded px-2 py-1">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="font-mono text-slate-100">
        {typeof v === "number" ? v.toFixed(2) : v}
      </div>
    </div>
  );
}
