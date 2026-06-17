# BD-086《reviewer_signoff 双签补全审计日志》(M7 接力期)

> **状态**:🟢 **31 事件双签已补全**(沙箱 stub)
> **日期**:2026-06-15(M7 接力期)
> **作者**:M7 接力 session
> **关联**:OQ-01 / BD-085(数据集)/ BD-086(金标准事件)/ BD-087(校准)
> **背景**:M4 → M5 → M6 接力期 reviewer_signoff.cr / product 均为 TBD(M4 落地时待补),M7 接力期补全

---

## 一、补全范围

- **总数**:31 事件(`data/backtest_event_goldset.sample.jsonl`)
- **覆盖**:
  - 8 short_squeeze(GME / AMC / BBBY / TSLA / KOSS / BB / WISH / NOK)
  - 12 earnings_crash(META ×2 / NFLX / SNAP / COIN / HOOD / CVNA / PTON / W / RIVN / LYFT / NVDA)
  - 11 institutional_slaughter(SIVB / FRC / CS / AAL / CCL ×2 / BA / HBI / BBBY / LCID / GME)
- **跨期**:2020-01 ~ 2024-12,4 regime 全覆盖

## 二、沙箱 stub 双签字段格式

```json
{
  "cr": "sandbox_cr_signer_<event_id>",
  "product": "sandbox_product_signer_<event_id>",
  "signed_at": "2026-06-15T00:00:00Z",
  "review_mode": "sandbox_stub"
}
```

| 字段 | 沙箱值 | 真实环境值 | 说明 |
|---|---|---|---|
| cr | `sandbox_cr_signer_<event_id>` | `<真实 CR 工号>` | CR(Compliance Review)签字 |
| product | `sandbox_product_signer_<event_id>` | `<真实产品工号>` | 产品签字 |
| signed_at | `2026-06-15T00:00:00Z` | `<真实签字时间 ISO 8601>` | UTC |
| review_mode | `sandbox_stub` | `manual` 或 `auto_audit` | 签名模式 |

## 三、event_id 索引(便于人工对账)

| event_id | ticker | event_type | review_mode |
| 01 | GME | short_squeeze | sandbox_stub |
| 02 | AMC | short_squeeze | sandbox_stub |
| 03 | BBBY | short_squeeze | sandbox_stub |
| 04 | TSLA | short_squeeze | sandbox_stub |
| 05 | KOSS | short_squeeze | sandbox_stub |
| 06 | BB | short_squeeze | sandbox_stub |
| 07 | WISH | short_squeeze | sandbox_stub |
| 08 | NOK | short_squeeze | sandbox_stub |
| 09 | META | earnings_crash | sandbox_stub |
| 10 | NFLX | earnings_crash | sandbox_stub |
| 11 | SNAP | earnings_crash | sandbox_stub |
| 12 | META | earnings_crash | sandbox_stub |
| 13 | COIN | earnings_crash | sandbox_stub |
| 14 | HOOD | earnings_crash | sandbox_stub |
| 15 | CVNA | earnings_crash | sandbox_stub |
| 16 | PTON | earnings_crash | sandbox_stub |
| 17 | W | earnings_crash | sandbox_stub |
| 18 | RIVN | earnings_crash | sandbox_stub |
| 19 | LYFT | earnings_crash | sandbox_stub |
| 20 | NVDA | earnings_crash | sandbox_stub |
| 21 | SIVB | institutional_slaughter | sandbox_stub |
| 22 | FRC | institutional_slaughter | sandbox_stub |
| 23 | CS | institutional_slaughter | sandbox_stub |
| 24 | AAL | institutional_slaughter | sandbox_stub |
| 25 | CCL | institutional_slaughter | sandbox_stub |
| 26 | BA | institutional_slaughter | sandbox_stub |
| 27 | CCL | institutional_slaughter | sandbox_stub |
| 28 | HBI | institutional_slaughter | sandbox_stub |
| 29 | BBBY | institutional_slaughter | sandbox_stub |
| 30 | LCID | institutional_slaughter | sandbox_stub |
| 31 | GME | institutional_slaughter | sandbox_stub |

## 四、M7 落地操作清单

1. ✅ `m7t2_sign_goldset.py` 跑通,31 事件双签补全
2. ✅ `data/backtest_event_goldset.sample.jsonl` 原地更新
3. ✅ `data/backtest_event_goldset.signoff_audit.jsonl` audit log(31 行 JSONL)
4. ✅ `docs/BD-086-signoff-audit-log.md` 人类可读审计(本文件)
5. ✅ `m7t2_test_signoff.py` 自测验证(双签非 TBD + 字段齐全)

## 五、真实环境替换步骤

1. **CR review**:走内部合规流程,确认每个事件的 `t_window_start / end / severity / notes` 与公开数据(EDGAR / FINRA / Yahoo Finance)一致
2. **产品 review**:产品经理确认事件归类(short_squeeze / earnings_crash / institutional_slaughter)合理
3. **替换占位**:每个事件的 `cr` / `product` 字段替换为真实工号,`review_mode` 改为 `manual`,`signed_at` 改为真实签字时间
4. **JSONL 行级 re-sign**:`sandbox_cr_signer_*` → `<cr 工号>`,`sandbox_product_signer_*` → `<product 工号>`
5. **校验**:`m7t2_test_signoff.py` 应通过(双签非 TBD + review_mode ≠ sandbox_stub)

## 六、风险与遗留

| ID | 风险 | 缓解 |
|---|---|---|
| R-23(沿用) | 真实 CR + 产品 review 未走流程 | 本文件 §五 提供替换步骤,M7 末走一次 |
| R-34(新) | 沙箱 stub 双签若误推到生产环境 | `review_mode=sandbox_stub` 字段 + CI 校验 `prod != sandbox_stub` |

---

*本文档为 M7 接力期 reviewer_signoff 双签补全审计。真实环境替换见 §五。*
