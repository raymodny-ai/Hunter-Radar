# Freeze Diff 增量校验操作手册(V1.5.8 m16t4)

> V1.5.8 接力期 m16t4:freeze_check 增量 diff 模式
>
> 用于 V1.5.X → V1.5.X+1 升级时,自动检测 freeze 文档变更(added / removed / changed 端点)
>
> 关联:
> - [openapi-frozen-v1.5.4.md](./openapi-frozen-v1.5.4.md) — 现行 freeze
> - [openapi-frozen-v1.5.4.json](./openapi-frozen-v1.5.4.json) — 机器可读
> - [freeze-check-runbook.md](./freeze-check-runbook.md) — C-3 9 校验操作手册
> - [V1.5.7-handoff.md](./V1.5.7-handoff.md) — V1.5.7 收尾报告
> - `backend/scripts/freeze_check.py` — 工具(9 校验 + diff 模式)

---

## 一、概述

V1.5.8 接力期 m16t4 扩展 `freeze_check.py` 加 **diff 模式**(`--diff --prev v1.5.4 --curr v1.5.5`):

- **默认模式**(原 9 校验):校验单版本 freeze 完整性
- **diff 模式**(本手册):对比两个 freeze 文档,检测变更端点

输出报告:
- `docs/freeze-diff-report-{prev}_to_{curr}.json` — 机器可读(added/removed/changed 列表)
- `docs/freeze-diff-report-{prev}_to_{curr}.md` — 人可读(汇总表)

---

## 二、diff 模式核心能力

### 2.1 3 类变更检测

| 类别 | 含义 | 示例 |
|------|------|------|
| **added** | 在 curr 不在 prev | 新增端点 `/api/v1.5/admin/audit-log` |
| **removed** | 在 prev 不在 curr | 删除端点 `/api/v1.4/legacy-endpoint` |
| **changed** | 都在但 summary 改了 | `summary` 文本变化 |

### 2.2 端点键

`(path, method)` 唯一标识:
- 例:`(/api/v1/etl/run, POST)` vs `(/api/v1/etl/run, GET)` 是不同端点

### 2.3 文档结构兼容

支持 2 种 freeze 文档结构:

1. **V1.5.4 实际格式**:`doc.endpoints = [{path, method, summary, ...}, ...]`
2. **标准 OpenAPI**:`doc.paths = {path: {method: {summary, ...}, ...}, ...}`

diff 函数 `_extract_endpoints()` 自动适配两种结构。

---

## 三、调用示例

### 3.1 基本调用

```bash
# diff v1.5.4 → v1.5.5
py -m scripts.freeze_check --diff --prev v1.5.4 --curr v1.5.5

# diff v1.5.5 → v1.5.6
py -m scripts.freeze_check --diff --prev v1.5.5 --curr v1.5.6
```

### 3.2 退出码

- `0` — diff 成功完成(无论是否有变更,都不是 error)
- `2` — freeze 文档不存在(--prev 或 --curr 文件缺失)

### 3.3 缺参数错误

```bash
# 缺 --prev / --curr
$ py -m scripts.freeze_check --diff
[freeze_check] --diff 模式必须传 --prev 和 --curr
(exit 2)
```

---

## 四、报告样例

### 4.1 JSON 报告

```json
{
  "prev_version": "v1.5.4",
  "curr_version": "v1.5.5",
  "prev_total": 56,
  "curr_total": 58,
  "added": [
    {"path": "/api/v1/admin/audit-log", "method": "GET", "summary": "审计日志"},
    {"path": "/api/v1/admin/audit-log", "method": "POST", "summary": "审计日志"}
  ],
  "removed": [],
  "changed": [
    {
      "path": "/api/v1/etl/run",
      "method": "POST",
      "prev_summary": "ETL run",
      "curr_summary": "ETL run (V1.5.5 super_admin 校验)"
    }
  ],
  "summary": {"added": 2, "removed": 0, "changed": 1}
}
```

### 4.2 Markdown 报告

```markdown
# Freeze Diff Report — v1.5.4 → v1.5.5

> 源端点: 56 → 目标端点: 58

## 汇总
- added: 2
- removed: 0
- changed: 1

## 新增端点 (added)
| path | method | summary |
|------|--------|---------|
| `/api/v1/admin/audit-log` | GET | 审计日志 |
| `/api/v1/admin/audit-log` | POST | 审计日志 |

## 删除端点 (removed)
(无删除)

## 修改端点 (changed)
| path | method | prev_summary | curr_summary |
|------|--------|--------------|--------------|
| `/api/v1/etl/run` | POST | ETL run | ETL run (V1.5.5 super_admin 校验) |
```

---

## 五、CI / pre-commit 集成

### 5.1 CI 工作流

在 `.github/workflows/ci.yml` 中追加 diff 检查 step:

```yaml
- name: Freeze diff check (V1.5.4 → V1.5.5)
  run: |
    cd backend
    python -m scripts.freeze_check --diff --prev v1.5.4 --curr v1.5.5
```

### 5.2 pre-commit hook

在 `scripts/pre_commit.py` 中加 diff 检查(在 freeze 文档变更时):

```python
# freeze_check 模式跑完后,自动跑 diff(如果 openapi-frozen 变更)
subprocess.run([
    sys.executable, "-B", "-m", "scripts.freeze_check",
    "--diff", "--prev", "v1.5.4", "--curr", "v1.5.5",
])
```

---

## 六、限制与边界

### 6.1 已知不支持

- 不对比 `parameters` / `requestBody` / `responses`(只对比 `summary`)
- 不递归对比嵌套对象(只对比 `summary` 字符串)
- 不识别端点重命名(只识别 path + method 变化)

### 6.2 后续增强(V1.5.9+ 候选)

- `--diff-fields` 参数:选择对比哪些字段
- `--diff-format` 参数:选择输出格式(json / yaml)
- `--fail-on-change` 模式:有变更返非 0(用于强制审核场景)

---

## 七、故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `freeze 文档不存在: docs/openapi-frozen-v1.5.5.json` | curr 版本还没 freeze | 先创建 freeze 文档,再 diff |
| `added=0 removed=0 changed=0` | prev 和 curr 完全一致 | 检查文件内容是否真的不同 |
| `summary 全是 ""` | freeze 文档用 paths 结构但 _extract_endpoints 没正确解析 | 已支持,但请检查 V1.5.4 实际格式 |

---

## 八、关联工具

- `scripts/freeze_check.py` — 9 校验 + diff 模式(本工具)
- `scripts/m16t4_test_freeze_diff.py` — diff 模式 25 测点自测
- `scripts/m8t1_test_regression.py` — m8t1 聚合 runner(含 m16t4)
- `docs/freeze-check-runbook.md` — 9 校验模式操作手册

---

> V1.5.8 接力期 m16t4 freeze diff 增量校验 — ONLINE-READY
> 工具: `backend/scripts/freeze_check.py --diff --prev <v> --curr <v>`
