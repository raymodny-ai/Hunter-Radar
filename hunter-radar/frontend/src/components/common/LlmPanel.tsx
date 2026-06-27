import { useState, useRef, useEffect } from "react";
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

/** 默认量化风控分析师提示词 */
const DEFAULT_PROMPT = `你现在是一位拥有20年经验的华尔街量化风控分析师（Quantitative Risk Analyst）。你的分析风格极其严谨、客观、保守，始终将"风险控制"放在首位。从不提供买卖建议（No Financial Advice），只提供基于数据的多维共振事实和概率性推演。

我将为你提供一份由我自研的量化雷达系统（Hunter Radar）产出的近期美股市场及特定标的的数据。这些数据涵盖了过去约 30 个交易日的情况。

### 📊 第一部分：系统指标定义（请严格基于以下定义进行分析，不要自行脑补）
1. **Market Regime (市场门控)**: 基于VIX/SPX均线计算。分为"正常(Normal)"或"恐慌(Panic)"。这是所有分析的大前提。
2. **Threat Score (威胁评分)**: 综合了4个子模块的风险打分。分数越高，短期做空或下行风险越大。
3. **Options Anomaly (期权异常)**: 监测末日Put期权异动、OI（未平仓合约）突增及Vol/OI比率。代表聪明钱（Smart Money）的短期押注。
4. **Short Iceberg (做空水位)**: 结合暗池(ATS)做空比例和Z-Score，反映机构做空力量的隐蔽聚集程度。
5. **Divergence (量价背离)**: 价格走势与做空量斜率的背离状态机，用于捕捉潜在的趋势反转或加速点。
6. **Ultimate Alert (终极警报)**: 当以上多个模块在同一天内发生共振（Resonance）时触发，属于高置信度风险信号。

### 📥 第二部分：今日数据输入
{{DATA_INPUT}}

### 🧠 第三部分：分析原则与强制约束（Crucial Constraints）
1. **自上而下（Top-Down）**: 必须首先评估 \`Market Regime\`。如果大盘处于"恐慌"状态，对个股的看空信号权重必须放大，看多信号权重必须降低。
2. **多维共振（Resonance over Noise）**: 单一指标的异常可能是噪音（例如仅有期权异动但无做空水位配合）。只有当 Threat Score、Options Anomaly 和 Short Iceberg 出现同向共振（或触发 Ultimate Alert）时，才可判定为有效信号。
3. **短期局限性（Short-Term Window）**: 我们的数据窗口目前为 30 个交易日。严禁做出中长期的宏观预测，你的分析结论必须限制在"未来1-5个交易日的短期动能与风险揭示"上。
4. **极度保守的措辞**: 禁用"将会"、"确定"、"买入/卖出"等词汇。强制使用"数据暗示(suggests)"、"呈现高置信度偏离(high-confidence divergence)"、"风险敞口扩大(increased risk exposure)"、"值得警惕(warrants caution)"等客观表述。

### 📝 第四部分：输出格式要求
请以结构化的报告形式输出你的分析结果，包含以下几个部分：
1. **Macro & Regime (市场环境评估)**：一句话总结当前大盘情绪及对个股的压制/支撑作用。
2. **Top Risk Radars (核心风险标的)**：选出数据中最值得关注的 1-3 只标的，列出其异常指标。
3. **Deep Dive Analysis (深度分析)**：针对核心标的，解释为何它的各项数据构成了"共振"。（例如：价格虽创新高，但 Short Iceberg 的 Z-Score 达历史极值，且 Put OI 激增）。
4. **Blind Spots (盲点与数据局限)**：基于你作为严谨分析师的角度，指出当前数据中缺失了什么信息（例如即将到来的财报、宏观数据发布等），作为保守的风险提示。`;

const SAVED_PROMPTS = [
  { label: "📊 完整量化风控报告", prompt: DEFAULT_PROMPT },
  { label: "做空资金流向", prompt: "请分析该标的的做空资金流向和技术面异常" },
  { label: "期权异常行为", prompt: "请分析该标的的期权市场异常行为" },
  { label: "短期风险等级", prompt: "综合评估该标的的短期风险等级" },
  { label: "轧空风险", prompt: "该标的是否存在做空轧空风险?" },
];

export function LlmPanel({ ticker, visible, onClose, context }: LlmPanelProps) {
  const [model, setModel] = useState("deepseek-v4-pro");
  const [promptText, setPromptText] = useState(DEFAULT_PROMPT);
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (visible) {
      setOutput("");
      setError(null);
      setPromptText(DEFAULT_PROMPT);
    }
  }, [visible]);

  useEffect(() => {
    if (output && outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const analyze = async (text?: string) => {
    const finalPrompt = text ?? promptText;
    if (!finalPrompt.trim()) return;
    setLoading(true);
    setError(null);
    setOutput(`[${model}] 正在分析 ${ticker}…`);
    try {
      const res = await fetch("/api/v1/llm/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker,
          model,
          prompt: finalPrompt,
          context: context || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(`API ${res.status}: ${err}`);
      }
      const data = await res.json();
      setOutput(data.content);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setOutput(`❌ 分析失败: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl">
        {/* 标题栏 */}
        <header className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <span>🧠</span> LLM 分析 · <span className="font-mono text-sky-300">{ticker}</span>
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
            <label className="text-xs text-slate-400">模型:</label>
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
          <div className="flex flex-wrap gap-1.5">
            {SAVED_PROMPTS.map((p, idx) => (
              <button
                key={idx}
                onClick={() => setPromptText(p.prompt)}
                disabled={loading}
                className={`text-xs px-2 py-1 rounded border disabled:opacity-50 ${
                  promptText === p.prompt
                    ? "bg-indigo-700 text-indigo-100 border-indigo-500"
                    : "bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* 提示词输入框（始终可编辑） */}
        <div className="px-5 py-2 border-b border-slate-800">
          <div className="flex gap-2">
            <textarea
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              placeholder="输入分析提示词…"
              rows={3}
              className="flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 placeholder-slate-500 resize-none font-mono"
            />
            <button
              onClick={() => analyze()}
              disabled={loading || !promptText.trim()}
              className="px-4 py-2 self-end rounded bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium disabled:opacity-50"
            >
              {loading ? "分析中…" : "分析"}
            </button>
          </div>
        </div>

        {/* 输出区域 */}
        <div
          ref={outputRef}
          className="flex-1 overflow-y-auto px-5 py-4 text-sm leading-relaxed whitespace-pre-wrap"
          style={{ minHeight: "200px", maxHeight: "400px" }}
        >
          {!output && !error && (
            <div className="text-slate-500 text-center py-10">
              点击上方快捷标签或输入提示词开始分析
            </div>
          )}
          {error && (
            <div className="text-red-400 mb-2">
              <span className="font-bold">⚠ 错误:</span> {error}
            </div>
          )}
          {output && !output.startsWith("[") && (
            <div className="text-slate-200">{output}</div>
          )}
          {output && output.startsWith("[") && loading && (
            <div className="text-slate-400">{output}</div>
          )}
        </div>

        {/* 底部信息 */}
        <div className="px-5 py-2 border-t border-slate-800 text-xs text-slate-500 flex justify-between items-center">
          <span>点击快捷标签替换提示词 · 可自由编辑</span>
          {output && !loading && (
            <button
              onClick={() => navigator.clipboard.writeText(output)}
              className="text-sky-400 hover:text-sky-300"
            >
              复制
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
