# Freeze Check Runbook — V1.5.7 接力期 OpenAPI freeze 自动化操作手册

> V1.5.7 接力期 m15t1(C-3 候选)落地:OpenAPI freeze 自动化校验工具 + 操作手册。
>
> 关联:
> - [scripts/freeze_check.py](../backend/scripts/freeze_check.py) — 9 项校验工具
> - [scripts/m15t1_test_freeze_automation.py](../backend/scripts/m15t1_test_freeze_automation.py) — 25 测点自测
> - [openapi-frozen-v1.5.4.md](./openapi-frozen-v1.5.4.md) — 现行 freeze(V1.5.4 接力期 m12)
> - [openapi-frozen-v1.5.4.json](./openapi-frozen-v1.5.4.json) — 机器可读

---

## 一、目的

每次 V 版本 freeze 时,自动校验 9 项硬性要求(端点数量、super_admin 列表、relay tasks 状态、admin 端点 docstring 等),避免人工疏漏,固化 freeze 状态机。

落地后:
- 每次 `git tag v1.5.X` 之前必跑 `freeze_check.py`
- 校验通过 → 生成 `freeze-check-report-v1.5.X.{json,md}` → 提交到 git
- 校验失败 → 阻断 freeze,人工修复后重跑

---

## 二、9 项校验清单

| § | 校验项 | 数据源 | 失败时排查 |
|---|------|--------|----------|
| 1 | `freeze_doc_exists` | `docs/openapi-frozen-{v}.md` + `.json` 双文档 | 双文档必须同步建/改 |
| 2 | `freeze_version_field` | JSON 顶字段 `freeze_version` | JSON 头字段必须 == 版本号 |
| 3 | `endpoints_total` | JSON `endpoints_total`(默认 56) | 端点增删必须更新此字段 |
| 4 | `super_admin_endpoints` | JSON `super_admin_endpoints[]` | V1.5.4+ 至少含 `/admin/webhook/replay` |
| 5 | `endpoint_review_meta` | JSON `endpoint_review_meta[]` | 4 admin 端点 + 1 catch_all 段 |
| 6 | `relay_tasks_complete` | JSON `v{VER}_relay_tasks` | 该 V 版本下所有 relay task 状态 == COMPLETE |
| 7 | `status_online_ready` | JSON `status` | freeze 落地前 `status=ONLINE-READY` |
| 8 | `admin_review_meta_in_code` | `backend/app/api/admin.py` 4 端点 docstring | 4 admin 端点必须含 `### REVIEW META` 段 |
| 9 | `m8t1_aggregate` | 子进程跑 `m8t1_test_regression` | m8t1 跑全量 0 失败(默认 1177/1177) |

---

## 三、调用方式

### 3.1 基础调用(推荐)

```powershell
cd "d:\Financial Project\Hunter Radar\hunter-radar\backend"
py -B -m scripts.freeze_check
```

默认校验 V1.5.4(当前 ONLINE-READY 状态)。

### 3.2 自定义版本

```powershell
py -B -m scripts.freeze_check --version v1.5.5
```

校验 V1.5.5(下一次 freeze)。

### 3.3 跳过 m8t1(快速校验)

```powershell
py -B -m scripts.freeze_check --skip-m8t1
```

跳过 §9 m8t1 子进程(节省 30~60s),用于开发期频繁校验。

### 3.4 期望输出

```
Freeze check: v1.5.4
  [PASS] §1 freeze_doc_exists: openapi-frozen-v1.5.4.md + .json 均存在
  [PASS] §2 freeze_version_field: freeze_version=v1.5.4
  [PASS] §3 endpoints_total: endpoints_total=56
  [PASS] §4 super_admin_endpoints: super_admin_endpoints=[...]
  [PASS] §5 endpoint_review_meta: endpoint_review_meta: 4 admin + 1 catch-all
  [PASS] §6 relay_tasks_complete: v154_relay_tasks: 3 task 全部 COMPLETE
  [PASS] §7 status_online_ready: status=ONLINE-READY
  [PASS] §8 admin_review_meta_in_code: admin.py 4 端点 docstring 均含 REVIEW META
  [PASS] §9 m8t1_aggregate: m8t1 1177/1177 ALL PASSED
=======================================================================
[freeze_check] v1.5.4 ALL CHECKS PASSED
  报告: freeze-check-report-v1.5.4.json + freeze-check-report-v1.5.4.md
```

退出码: 0 = 全部通过, 1 = 至少 1 项失败。

---

## 四、报告输出

工具自动生成 2 份报告到 `docs/`:

| 文件 | 用途 | 何时提交 |
|------|------|---------|
| `freeze-check-report-{v}.json` | 机器可读,9 项校验明细 + 校验时间 | 每次 freeze 必提交 |
| `freeze-check-report-{v}.md` | 人可读,Markdown 表格 | 每次 freeze 必提交 |

报告样例(节选):

```json
{
  "freeze_version": "v1.5.4",
  "checked_at": "2026-06-15T...",
  "all_pass": true,
  "checks": [
    {"check": "§1 freeze_doc_exists", "passed": true, "detail": "..."},
    ...
  ]
}
```

---

## 五、CI 集成(可选,P2)

GitHub Actions workflow(`.github/workflows/freeze-check.yml`):

```yaml
name: freeze-check
on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      version:
        description: 'freeze 版本'
        required: true
        default: 'v1.5.4'

jobs:
  freeze-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Run freeze check
        run: py -B -m scripts.freeze_check --version ${{ github.event.inputs.version || github.ref_name }}
```

> 注:本节 P2 实施,本期 m15t1 仅本地脚本 + 25 测点,CI 集成留 V1.5.8+ 评估。

---

## 六、故障排查

### Q1: §3 endpoints_total != 56

**原因**: 端点增删未同步更新 JSON。

**修复**:
1. 检查 `backend/app/api/` 实际端点数量(`@router.post/.get/.delete` 等)
2. 更新 `openapi-frozen-{v}.json` 的 `endpoints_total` 字段
3. 重跑 `freeze_check.py`

### Q2: §4 super_admin_endpoints 为空

**原因**: V1.5.4+ 必填,缺 `require_super_admin_role` 端点。

**修复**:
1. 检查 `backend/app/api/admin.py` 是否含 `require_super_admin_role` 调用
2. 更新 JSON `super_admin_endpoints[]` 列表
3. 重跑

### Q3: §6 relay_tasks 有非 COMPLETE

**原因**: 该 V 版本下某 relay task 状态未更新为 COMPLETE。

**修复**:
1. 完成 relay task 实现
2. 更新 JSON `v{VER}_relay_tasks.{task}.status = "COMPLETE"`
3. 重跑

### Q4: §8 admin.py 缺 REVIEW META

**原因**: admin 端点 docstring 未含 `### REVIEW META` 段。

**修复**:
1. 打开 `backend/app/api/admin.py`
2. 给 4 admin 端点(`post_etl_run` / `post_backtest_run` / `get_backtest_result` / `post_webhook_replay`)docstring 末尾加:
   ```python
   ### REVIEW META (V1.5.4 m12t3)
   review_status: passes_v153 (or passes_v154)
   owner: platform-team
   last_reviewed: 2026-06-15
   ...
   ```
3. 重跑

### Q5: §9 m8t1 失败

**原因**: 56 脚本 / 1177 测点有失败。

**修复**:
1. 跑 `py -B -m scripts.m8t1_test_regression` 看具体失败脚本
2. 修复该脚本(参考失败测点输出)
3. 重跑 freeze_check

---

## 七、版本演进记录

| V 版本 | 接力期 | 端点数 | super_admin | C 候选 | 状态 |
|--------|--------|--------|------------|--------|------|
| v1.4 | M4 | 56 | 0 | - | ONLINE-READY |
| v1.4.1 | M5 | 56 | 0 | - | ONLINE-READY |
| v1.5 | M5-M8 | 56 | 0 | - | ONLINE-READY |
| v1.5.1 | M9 | 56 | 0 | - | ONLINE-READY |
| v1.5.2 | M10 | 56 | 0 | - | ONLINE-READY |
| v1.5.3 | M11 | 56 | 0 | - | ONLINE-READY |
| v1.5.4 | M12 | 56 | 1 | C-2/C-4/C-5 | ONLINE-READY |
| v1.5.5 | M13 | 56 | 1 | (m8t1 15 失败修复) | ONLINE-READY |
| v1.5.6 | M14 | 56 | 1 | C-1(reviewer_cli 拆分) | ONLINE-READY |
| v1.5.7 | M15 | 56 | 1 | C-3(freeze 自动化) | ONLINE-READY |

> V1.5.5 / V1.5.6 freeze 文档由本期 m15t1 同步生成(见 [openapi-frozen-v1.5.5.md](./openapi-frozen-v1.5.5.md) + [v1.5.6](./openapi-frozen-v1.5.6.md))。

---

## 八、下一阶段(V1.5.8+)

- P1: 启动 C-6 候选 — 静态分析 harness(把 m9/m10/m11/m12 整合到统一 self_test_harness 入口)
- P1: freeze_check.py 集成 GitHub Actions(见 §五 CI 集成)
- P2: freeze_check.py 支持 --diff 比对(自动对比 v{N} vs v{N-1} 端点增删)
