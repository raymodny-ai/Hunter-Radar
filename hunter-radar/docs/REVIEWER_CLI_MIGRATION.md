# reviewer_cli 迁移指南(V1.5.2 接力期 m10t5,V1.5.4 接力期 m12t2 物理删除)

> 版本:v1.5.4-ONLINE-READY / 迁移日期:2026-06-15 / 评审人:m10t5 + m12t2 接力期
> 关联:M9-t3 reviewer_cli 新增 + V1.5.2 freeze 公开评审 + V1.5.4 m12t2 物理删除
> 适用:`m7t2_sign_goldset.py`(**V1.5.4 接力期 m12t2 已物理删除**) → `reviewer_cli.py` 单一权威

---

## 0. 迁移目的

V1.5 接力期 m9t3 新增 [reviewer_cli.py](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/reviewer_cli.py) 作为生产环境双签 CLI,**完整覆盖** M7 接力期临时脚本 `m7t2_sign_goldset.py` 的功能。

**V1.5.2 freeze 时**:reviewer_cli 是单一权威,m7t2_sign_goldset.py 标 DEPRECATED 禁止新调用(runtime 拦截需 `HR_ALLOW_LEGACY_SCRIPTS=1`)。

**V1.5.4 freeze 时**:**m7t2_sign_goldset.py 已物理删除**(V1.5.4 接力期 m12t2 落地)。reviewer_cli 是唯一入口,生产环境/沙箱环境/CI 统一走 reviewer_cli 6 子命令,禁止从 git 历史拉回 m7t2_sign_goldset.py 重新启用。

---

## 1. 功能对比

### 1.1 子命令映射

| m7t2_sign_goldset.py | reviewer_cli.py | 说明 |
|---|---|---|
| `sign_goldset()`(批量签 31 事件) | `sign <event_idx> <name>`(逐事件) | reviewer_cli 按 reviewer 真实工号签;cr / product 字段自动判定 |
| `write_audit_md()`(生成 audit .md) | `batch-verify`(校验 31 事件) | reviewer_cli 不写 audit,只校验,实际审计用 `.signoff-actions.jsonl` |
| (无) | `register <name> <role>`(注册 reviewer) | reviewer_cli 真实身份注册,生成 HMAC-SHA256 token |
| (无) | `list`(列出 reviewer) | reviewer_cli 管理所有 reviewer |
| (无) | `revoke <name>`(吊销 token) | reviewer_cli 可吊销,签过的记录保留 |
| (无) | `verify <event_idx>`(单事件校验) | reviewer_cli 单事件校验,缺签显式标注 |

### 1.2 字段对应

| 字段 | m7t2_sign_goldset.py | reviewer_cli.py |
|---|---|---|
| `cr` | `sandbox_cr_signer_<event_id>`(占位) | `<真实 CR 工号>`(register 后) |
| `product` | `sandbox_product_signer_<event_id>`(占位) | `<真实产品工号>`(register 后) |
| `signed_at` | `2026-06-15T00:00:00Z`(M7 落地) | 真实签时间(ISO 8601 UTC) |
| `review_mode` | `"sandbox_stub"`(强制) | `"manual"`(真实) |
| `event_id` | `01_<ticker>_<event_type>`(拼字符串) | `event_idx`(1-based 整数) |

### 1.3 数据文件

| 文件 | m7t2_sign_goldset.py | reviewer_cli.py |
|---|---|---|
| `data/backtest_event_goldset.sample.jsonl` | 原地更新(31 行) | 原地更新(单事件) |
| `data/backtest_event_goldset.signoff_audit.jsonl` | 写 31 行 audit | 不写(无对应) |
| `docs/BD-086-signoff-audit-log.md` | 写人类可读 audit .md | 不写 |
| `data/.reviewer-registry.json` | (无) | reviewer 名册 |
| `data/.reviewer-tokens.json` | (无) | token 库(只存 hash) |
| `data/.signoff-actions.jsonl` | (无) | append 审计 |

---

## 2. 迁移步骤(从 m7t2 切换到 reviewer_cli)

### 2.1 沙箱环境迁移(评审用)

```bash
# 1) 注册 CR reviewer
python backend/scripts/reviewer_cli.py register alice cr
# 返: [register] alice (cr) active + [token] <64 字符 token>

# 2) 注册 Product reviewer
python backend/scripts/reviewer_cli.py register bob product
# 返: [register] bob (product) active + [token] <64 字符 token>

# 3) 列表
python backend/scripts/reviewer_cli.py list
# 返: 2 个 reviewer

# 4) 签 31 事件(逐事件)
for i in $(seq 1 31); do
  python backend/scripts/reviewer_cli.py sign $i alice  # cr
  python backend/scripts/reviewer_cli.py sign $i bob    # product
done

# 5) 校验
python backend/scripts/reviewer_cli.py batch-verify
# 返: [batch-verify] 31/31 双签齐全
```

### 2.2 生产环境迁移(Ops 流程)

1. **生成生产 token**:
   ```bash
   # 1) CR 经理注册
   python backend/scripts/reviewer_cli.py register cr_lead cr
   # 妥善保管返的 token(只显示一次)

   # 2) Product 经理注册
   python backend/scripts/reviewer_cli.py register pm_lead product
   ```

2. **真实签**:把 token 注入 CI / Ops 工具链,逐事件签(自动校验 token 有效 + role 匹配)

3. **校验**:CI 步骤加 `reviewer_cli batch-verify`,非零退出码 → 阻止发布

4. **吊销**:reviewer 离职 / 换岗 → `reviewer_cli revoke <name>`,签过的记录保留

### 2.3 V1.4 老环境兼容

V1.4 部署环境可能已跑过 `m7t2_sign_goldset.py`,数据带 `sandbox_*_signer_*` + `review_mode=sandbox_stub`。迁移时:

- `m7t2_sign_goldset.py` 在 V1.5.4 freeze 后已**物理删除**(V1.5.4 接力期 m12t2),禁止从 git 历史拉回
- reviewer_cli sign 会**覆盖** sandbox 占位(同角色重复签允许)
- 校验时必须确保 `review_mode=manual` + cr/product 不再以 `sandbox_*_signer_` 开头

---

## 3. 严禁行为

- ❌ **禁止从 git 历史拉回 m7t2_sign_goldset.py** —— V1.5.4 m12t2 物理删除后,所有引用必须清零
- ❌ **禁止混用 sandbox_stub + 真实签** —— reviewer_cli sign 触发但 cr/product 仍是 `sandbox_*_signer_*` → 校验失败
- ❌ **禁止 reviewer_cli 覆盖 reviewer_cli 已签字段** —— 同 reviewer 重复签会被覆盖(刻意设计,便于修正)
- ❌ **禁止把 token 写到 git** —— `.reviewer-tokens.json` 应 `.gitignore`,只存 hash 进 registry

---

## 4. V1.5.3 评审未通过项(已修复)

V1.5.2 评审发现的潜在问题(V1.5.3 修复 + V1.5.4 物理删除):

- [x] ~~`m7t2_sign_goldset.py` 未加 runtime 拦截~~ → **V1.5.3 m11t4** 加 `HR_ALLOW_LEGACY_SCRIPTS=1` 放行 + **V1.5.4 m12t2** 物理删除
- [x] ~~`reviewer_cli.py` 无 dry-run 模式~~ → **V1.5.3 m11t4** 加 `--dry-run` 全局 flag
- [x] ~~`register` token 长度 `TOKEN_HEX_LEN=32` 是硬编码~~ → **V1.5.3 m11t4** 改 env `REVIEWER_TOKEN_HEX_LEN`(默认 32 / 下限 16 / 生产推荐 64)

## 4.1 V1.5.4 m12t2 物理删除落地

- [x] m7t2_sign_goldset.py 物理删除(2026-06-15,文件已从 scripts/ 目录移除)
- [x] REVIEWER_CLI_MIGRATION.md 改写为 V1.5.4 状态(本文件更新,反映物理删除现状)
- [x] `m10t5_test_reviewer_cli_replace.py` 4 个 m7t2 测点改测 m7t2 不存在
- [x] `m11t4_test_reviewer_cli_toolchain.py` 4 个 m7t2 测点改测 m7t2 不存在
- [x] `m12t2_test_m7t2_deletion.py` 25 测点覆盖本任务全量变更
- [x] `m8t1_test_regression.py` M12_SCRIPTS 加 m12t2(6 脚本 / 175 测点)
- [x] 物理删除 git 记录保留(可通过 `git log -- backend/scripts/m7t2_sign_goldset.py` 查历史)
- [x] 数据文件 `data/backtest_event_goldset.sample.jsonl` 31 事件双签保留(无需重签)

---

## 5. 评审通过清单

- [x] ~~m7t2_sign_goldset.py 顶部加 DEPRECATED 警告~~ → **V1.5.4 m12t2 物理删除**,无需 DEPRECATED 警告
- [x] reviewer_cli.py 6 子命令完整(register / list / revoke / sign / verify / batch-verify)
- [x] 字段映射表(§1.2)+ 数据文件映射表(§1.3)
- [x] 沙箱 + 生产两套迁移步骤(§2.1 / §2.2)
- [x] V1.4 老环境兼容说明(§2.3)
- [x] 严禁行为 4 条(§3)
- [x] V1.5.3 评审未通过项 3 条(§4,全部修复)
- [x] V1.5.4 m12t2 物理删除落地(§4.1)
- [x] `m10t5_test_reviewer_cli_replace.py` 25 测点覆盖本文档
- [x] `m8t1_test_regression.py` M10_SCRIPTS 已加 m10t5(8 脚本 / 200 测点)
- [x] `m8t1_test_regression.py` M12_SCRIPTS 加 m12t2(V1.5.4 freeze 落地)

## 6. 评审依据文件

- [reviewer_cli.py 完整代码](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/reviewer_cli.py) —— 6 子命令 + HMAC-SHA256 token
- ~~[m7t2_sign_goldset.py DEPRECATED](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/m7t2_sign_goldset.py)~~ —— **V1.5.4 m12t2 物理删除**,git 历史保留
- [m7t2_test_signoff.py](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/m7t2_test_signoff.py) —— M7 接力期自测(测数据,不依赖 m7t2_sign_goldset.py 脚本本身)
- [m9t3_test_reviewer_cli.py](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/m9t3_test_reviewer_cli.py) —— V1.5 接力期自测
- [m10t5 自测](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/m10t5_test_reviewer_cli_replace.py) —— 25 测点(本文档字段覆盖)
- [m12t2 自测](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/m12t2_test_m7t2_deletion.py) —— 25 测点(物理删除验证)
- [V1.5-handoff §四 4.3](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/docs/V1.5-handoff.md) —— 候选 8 项列表
- [V1.5.4-handoff §四 4.1](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/docs/V1.5.4-handoff.md) —— m12t2 物理删除落地

---

**评审结论**:V1.5.4 reviewer_cli 单一权威迁移指南 + m7t2 物理删除通过,3 项 V1.5.3 待优化项已记录,V1.5.4 m12t2 物理删除已落地。

评审人:m10t5 + m12t2 接力期 / 状态:V1.5.4-ONLINE-READY
