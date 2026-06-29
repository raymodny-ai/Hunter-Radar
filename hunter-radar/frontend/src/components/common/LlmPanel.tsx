/**
 * FE-137/138/139: LLM 面板 SSE 流式输出改造
 *
 * - FE-137: EventSource/SSE 逐字打字机效果 + Markdown 实时解析
 * - FE-138: 标的切换触发上下文自动注入
 * - FE-139: 底部持久化免责水印(不可关闭)
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";

interface LlmPanelProps {
  ticker: string;
  visible: boolean;
  onClose: () => void;
  context?: string;
}

const MODELS = [
  { id: "deepseek-v4-pro", label: "DeepSeek V4 Pro" },
  { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
];

const DEFAULT_PROMPT = `你现在是一位拥有20年经验的华尔街量化风控分析师（Quantitative Risk Analyst）。你的分析风格极其严谨、客观、保守，始终将"风险控制"放在首位。从不提供买卖建议（No Financial Advice），只提供基于数据的多维共振事实和概率性推演。

我将为你提供一份由我自研的量化雷达系统（Hunter Radar）产出的近期美股市场及特定标的的数据。这些数据涵盖了过去约 30 个交易日的情况。

### 📊 第一部分：系统指标定义（请严格基于以下定义进行分析，不要自行脑补）
1. **Market Regime (市场门控)**: 基于VIX/SPX均线计算。分为"正常(Normal)"或"恐慌(Panic)"。这是所有分析的大前提。
2. **Threat Score (威胁评分)**: 综合了4个子模块的风险打分。分数越高，短期做空或下行风险越大。
3. **四个子模块**: 期权异常(Options)、做空水位(Short)、量价背离(Divergence)、SEC内部人行为(Insider)。
4. **Signal Lifecycle (信号生命周期)**: init/red/yellow/gray/green 五态状态机。

### 📈 第二部分：数据
请基于以下数据，给出你的分析：
`;

/**
 * 简单 Markdown → HTML 转换(仅处理 heading/list/code-block/bold)
 */
function renderMarkdown(text: string): string {
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-slate-800 rounded p-2 text-xs font-mono my-1 overflow-x-auto">$2</pre>')
    .replace(/### (.*)/g, '<h3 class="text-sm font-bold mt-2 mb-1">$1</h3>')
    .replace(/## (.*)/g, '<h2 class="text-base font-bold mt-2 mb-1">$1</h2>')
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/^- (.*)/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/\n\n/g, "<br/>");
}

export function LlmPanel({ ticker, visible, onClose, context }: LlmPanelProps) {
  const { t } = useTranslation();
  const [model, setModel] = useState("deepseek-v4-pro");
  const [promptText, setPromptText] = useState(DEFAULT_PROMPT);
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (visible) {
      setOutput("");
      setError(null);
      setPromptText(DEFAULT_PROMPT);
    }
  }, [visible]);

  // 自动滚动到底部
  useEffect(() => {
    if (output && outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  // FE-138: 标的切换时自动分析
  useEffect(() => {
    if (visible && context) {
      analyze(promptText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, ticker]);

  const analyze = useCallback(
    async (text?: string) => {
      const finalPrompt = text ?? promptText;
      if (!finalPrompt.trim()) return;

      // 取消上一次请求
      if (abortRef.current) abortRef.current.abort();
      abortRef.current = new AbortController();

      setLoading(true);
      setError(null);
      setOutput("");

      try {
        const res = await fetch("/api/v1/llm/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticker,
            model,
            prompt: finalPrompt,
            context: context || undefined,
            stream: true, // 请求 SSE
          }),
          signal: abortRef.current.signal,
        });

        if (!res.ok) {
          const err = await res.text();
          throw new Error(`API ${res.status}: ${err}`);
        }

        const contentType = res.headers.get("content-type") || "";

        // FE-137: SSE 流式处理
        if (
          contentType.includes("text/event-stream") ||
          contentType.includes("text/plain")
        ) {
          const reader = res.body?.getReader();
          if (!reader) throw new Error("No response body");

          const decoder = new TextDecoder();
          let accumulated = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            // 解析 SSE events
            const lines = chunk.split("\n");
            for (const line of lines) {
              if (line.startsWith("data: ")) {
                const data = line.slice(6);
                if (data === "[DONE]") continue;
                try {
                  const parsed = JSON.parse(data);
                  const content =
                    parsed.choices?.[0]?.delta?.content ||
                    parsed.content ||
                    data;
                  accumulated += content;
                  setOutput(accumulated);
                } catch {
                  accumulated += data;
                  setOutput(accumulated);
                }
              } else if (line.trim() && !line.startsWith(":")) {
                // 非 SSE 格式,直接追加
                accumulated += line;
                setOutput(accumulated);
              }
            }
          }
        } else {
          // 非流式 fallback
          const data = await res.json();
          setOutput(data.content || JSON.stringify(data));
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        setOutput(`❌ ${t("llm.error")}: ${msg}`);
      } finally {
        setLoading(false);
      }
    },
    [ticker, model, promptText, context, t],
  );

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl">
        {/* 标题栏 */}
        <header className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <span>🧠</span> {t("llm.title")} · <span className="font-mono text-sky-300">{ticker}</span>
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-xl leading-none px-2"
          >
            ✕
          </button>
        </header>

        {/* 模型选择 + 快捷提示词 */}
        <div className="px-5 py-3 border-b border-slate-800 space-y-2">
          <div className="flex items-center gap-3">
            <label className="text-xs text-slate-400">{t("llm.model")}:</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200"
            >
              {MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <textarea
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            rows={3}
            className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 font-mono resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => analyze()}
              disabled={loading}
              className="px-3 py-1.5 rounded bg-indigo-700/60 hover:bg-indigo-600 border border-indigo-600/50 text-indigo-100 text-sm disabled:opacity-50 transition-colors"
            >
              {loading ? t("llm.analyzing") : t("llm.analyze")}
            </button>
            {loading && (
              <button
                onClick={() => abortRef.current?.abort()}
                className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm"
              >
                {t("llm.stop")}
              </button>
            )}
          </div>
        </div>

        {/* 输出区域 */}
        <div
          ref={outputRef}
          className="flex-1 overflow-y-auto px-5 py-3 text-sm text-slate-300 leading-relaxed prose-sm"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(output) }}
        />

        {/* FE-139: 持久化免责水印(不可关闭) */}
        <div className="px-5 py-2 bg-red-950/20 border-t border-red-900/30 text-[10px] text-red-400/80 flex items-center gap-2">
          <span>⚠</span>
          <span>{t("llm.disclaimer")}</span>
        </div>
      </div>
    </div>
  );
}
