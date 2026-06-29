/**
 * FE-141: AlertRuleForm — React Hook Form + Zod 条件构建器
 *
 * 条件组合:标的 + 指标 + 阈值 + 比较运算符
 * - Zod schema 校验
 * - 支持编辑已有规则 / 创建新规则
 * - 暗黑主题 Tailwind 样式
 */
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

/** Zod schema for alert rule */
export const alertRuleSchema = z.object({
  symbol: z.string().min(1, "symbolRequired").max(10),
  rule_type: z.enum(["threat_score", "short_ratio", "options_pcr", "divergence", "insider_sell"]),
  threshold: z.coerce.number().min(0).max(100),
  operator: z.enum([">=", "<=", ">", "<", "=="]),
});

export type AlertRuleFormData = z.infer<typeof alertRuleSchema>;

export interface AlertRuleFormProps {
  /** Pre-fill for editing */
  initial?: Partial<AlertRuleFormData>;
  onSubmit: (data: AlertRuleFormData) => void | Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

const RULE_TYPES = [
  "threat_score",
  "short_ratio",
  "options_pcr",
  "divergence",
  "insider_sell",
] as const;

const OPERATORS = [">=", "<=", ">", "<", "=="] as const;

export function AlertRuleForm({
  initial,
  onSubmit,
  onCancel,
  isLoading,
}: AlertRuleFormProps) {
  const { t } = useTranslation();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AlertRuleFormData>({
    resolver: zodResolver(alertRuleSchema),
    defaultValues: {
      symbol: initial?.symbol ?? "",
      rule_type: initial?.rule_type ?? "threat_score",
      threshold: initial?.threshold ?? 70,
      operator: initial?.operator ?? ">=",
    },
  });

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-3 bg-slate-800/80 rounded-lg p-4 border border-slate-700/50"
    >
      <h3 className="font-semibold text-sm">{t("alerts.form.title")}</h3>

      {/* Symbol */}
      <label className="block">
        <span className="text-xs text-slate-400">{t("alerts.form.symbol")}</span>
        <input
          {...register("symbol")}
          className="mt-1 w-full px-2 py-1 bg-slate-900 rounded text-slate-100 text-sm uppercase"
          placeholder="AAPL"
        />
        {errors.symbol && (
          <span className="text-xs text-red-400 mt-0.5">{t(`alerts.form.${errors.symbol.message}`)}</span>
        )}
      </label>

      {/* Rule Type */}
      <label className="block">
        <span className="text-xs text-slate-400">{t("alerts.form.ruleType")}</span>
        <select
          {...register("rule_type")}
          className="mt-1 w-full px-2 py-1 bg-slate-900 rounded text-slate-100 text-sm"
        >
          {RULE_TYPES.map((rt) => (
            <option key={rt} value={rt}>
              {t(`alerts.ruleTypes.${rt}`)}
            </option>
          ))}
        </select>
      </label>

      {/* Operator + Threshold */}
      <div className="flex gap-2">
        <label className="flex-1">
          <span className="text-xs text-slate-400">{t("alerts.form.operator")}</span>
          <select
            {...register("operator")}
            className="mt-1 w-full px-2 py-1 bg-slate-900 rounded text-slate-100 text-sm"
          >
            {OPERATORS.map((op) => (
              <option key={op} value={op}>{op}</option>
            ))}
          </select>
        </label>
        <label className="flex-1">
          <span className="text-xs text-slate-400">{t("alerts.form.threshold")}</span>
          <input
            type="number"
            {...register("threshold")}
            min={0}
            max={100}
            step={1}
            className="mt-1 w-full px-2 py-1 bg-slate-900 rounded text-slate-100 text-sm"
          />
          {errors.threshold && (
            <span className="text-xs text-red-400 mt-0.5">{t("alerts.form.thresholdError")}</span>
          )}
        </label>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={isLoading}
          className="px-3 py-1 rounded bg-hunter-red text-white text-sm disabled:opacity-50"
        >
          {isLoading ? t("common.loading") : t("alerts.form.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1 rounded bg-slate-700 text-slate-100 text-sm"
        >
          {t("alerts.form.cancel")}
        </button>
      </div>
    </form>
  );
}
