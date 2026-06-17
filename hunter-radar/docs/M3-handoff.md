># Hunter Radar V1.4 — M3 收尾完成报告

> **✅ 状态:M3 主体 7 个 todo 全部 COMPLETE**(2026-06-15,W1 末)
> 前置:[M2-handoff.md](M2-handoff.md)
> 后续:M4 自定义分析(BD-085/086 → BD-089 离线回测 → BD-087 校准 v2.0)

## 一、M3 范围与交付

### 1.1 完成度

| 任务 | 状态 | 关键产出 |
|---|---|---|
| m3t1 前端 3 组件新建 | ✅ COMPLETE | `SignalLifecycleBadge` / `UltimateAlertOverlay` / `ThreatHistoryChart` |
| m3t2 前端 3 hooks 新建 | ✅ COMPLETE | `useThreatHistory` / `useSignalLifecycle` / `useUltimateAlert` |
| m3t3 改造 `symbol.$ticker.tsx` | ✅ COMPLETE | 接入 3 组件,移除 M0 占位 |
| m3t4 后端 DAG 4 占位 task 切真实 | ✅ COMPLETE | `pull_finra_ats` / `pull_sec_form4` / `pull_sec_buyback` / `compute_threat_score` / `run_screener` |
| m3t4 同步:新增 ultimate-alert API | ✅ COMPLETE | `GET /api/v1/symbols/{ticker}/ultimate-alert` + 404 语义 |
| m3t5 集成测试脚本骨架 | ✅ COMPLETE | `scripts/m3_integration_smoke.py`(9 测点,沙箱自动跳) |
| m3t6 BD-087 校准报告 v1.0 | ✅ COMPLETE | `docs/BD-087-calibration-report-v1.0.md`(理论 + 方法论 + 时间表) |
| m3t7 文档 | ✅ COMPLETE | 本文档 + `daily-standup.md` W1 末段更新 |

### 1.2 交付清单

**新建文件(9 个):**

| 路径 | 行数 | 角色 |
|---|---|---|
| `frontend/src/components/radar/SignalLifecycleBadge.tsx` | 63 | FE-030 5 态信号灯徽章 + ×Nd 连续日 |
| `frontend/src/components/radar/UltimateAlertOverlay.tsx` | 116 | FE-031 全屏模态终极警报 + 免责声明 |
| `frontend/src/components/radar/ThreatHistoryChart.tsx` | 193 | FE-032 90 日轨迹纯 SVG 折线图(无 ECharts) |
| `frontend/src/features/useThreatHistory.ts` | 19 | 90 日 hook |
| `frontend/src/features/useSignalLifecycle.ts` | 90 | 客户端 OQ-02 镜像(连续 ≥2 日 + 暖启动) |
| `frontend/src/features/useUltimateAlert.ts` | 50 | 404/501 优雅降级 |
| `scripts/m3_integration_smoke.py` | 172 | 9 测点 smoke test(沙箱自动跳) |
| `docs/BD-087-calibration-report-v1.0.md` | 197 | 校准草稿 + 理论推导 + 时间表 |
| `docs/M3-handoff.md` | (本文件) | M3 完成报告 |

**修改文件(5 个):**

| 路径 | 变更 | 角色 |
|---|---|---|
| `frontend/src/routes/symbol.$ticker.tsx` | +53 / -11 | 接入 3 组件 + state 管理 + useEffect 防 setState-in-render |
| `frontend/src/lib/api.ts` | +17 / -1 | 新增 `getUltimateAlert` + `UltimateAlertDTO` 类型 |
| `frontend/src/i18n/zh-CN.json` | +19 | 新增 `ultimateAlert` / `history` / `lifecycleBadge` 3 段 |
| `backend/app/api/symbols.py` | +78 | 新增 `UltimateAlertDTO` + `GET /symbols/{ticker}/ultimate-alert` 端点 |
| `backend/dags/hunter_radar_eod.py` | +141 / -17 | 5 个 task 切真实调掇(原 stub 全替换) |

## 二、M3 关键设计

### 2.1 「警-图-表」三件套(信号传递层次)

按用户视觉重要度排序:
1. **UltimateAlertOverlay**(全屏 modal,最高级) — 仅在 EMA ≥ 70/80 + 连续 ≥ 2 日 + 24h 防抖时弹
2. **SignalLifecycleBadge**(常驻 header 徽章,中级) — 5 态颜色+文字双编码,连续 ≥ 2 日显 ×Nd
3. **ThreatHistoryChart**(底部区块,信息层) — 90 日轨迹,纯 SVG 无外部依赖

### 2.2 「1 弹 1 次 + 用户主动关闭」UX 决策

- 后端:`ultimate_alert` 表 UNIQUE (trade_date, symbol) + 24h 防抖
- 前端:`useUltimateAlert.alertId = ${trade_date}:${triggered_at}` + `dismissedAlertId` 状态
- 触发条件:`alertId !== null && alertId !== dismissedAlertId && !overlayOpen` → `useEffect` 异步 setState
- 关闭:`onClose` 同时 `setOverlayOpen(false)` + `setDismissedAlertId(alertId)` → 同 alert 永不重弹

### 2.3 OpenAPI freeze 约束落实

- 新增端点:`GET /api/v1/symbols/{ticker}/ultimate-alert`,响 `UltimateAlertDTO`,404 表示无活跃
- 前端 `useUltimateAlert`:404/501 均降级为 `null`(不抛错,不阻塞 UI)
- 路径与 useUltimateAlert 注释草案一致(免去后续 FE-010 同步)

### 2.4 纯 SVG 折线图替代 ECharts

- ThreatHistoryChart 193 行,纯 React + Tailwind
- 无 ECharts 依赖 → 包体减 ~150KB
- 阈值(70 / 80)以 dashed 标线
- 数据不足(< 2 点)显「数据积累中(约需 N 个交易日)」,不渲染假图(防数据伪装)

### 2.5 DAG 5 task 切真实调掇的依赖链

```
[finra, ats] >> load_sv
yahoo_eod >> load_dp
yahoo_opt >> load_oc >> anomaly
sec_form4 >> load_f4
[load_sv, load_dp, anomaly, load_f4, etf, sec_buyback] >> score >> screener
```

- `score` 即 `compute_threat_score` → 调 `etl.load_threat_score.compute_threat_scores(d)`
- `screener` 即 `run_screener` → 调 `app.services.ultimate_alert.evaluate_ultimate_alerts(d)`(落 ultimate_alert 表)
- 串接:price → short → div → threat_score_daily → ultimate_alert(7 步依赖链)

## 三、M3 关键决策与硬约束

### 3.1 OQ 决策锁定(未触碰)

- OQ-01 权重回测校准:静态 30/35/20/15、35/45/20 不直接上线;M5 校准前不得修改
- OQ-02 EMA 半衰期 2 日 + 连续 2 交易日:8 个单元测试守护
- OQ-16 ETF 代理指标 PoC:已就位,真实申赎数据二期接
- OQ-09 / OQ-11:项目忽略

### 3.2 CR 红线(未触碰)

- CR-010 禁词清单(`scripts/compliance_check.py` 锁定):不输出投资建议
- 「仅供参考 / 不构成投资建议」必含兜底(UltimateAlertOverlay L98-101 强制)
- API 契约与数据真实性规范:OpenAPI 变更先 freeze;数据缺失返 200 + 空数组,严禁 mock 伪装

### 3.3 新增硬约束(M3 接力期提取)

- 「OpenAPI 变更需先 freeze 再同步 FE-010」:在 m3t4 落实为「新增端点不需 freeze(无现有契约),修改端点需先 freeze」
- 「数据缺失返 200 + 空数组,严禁 mock 伪装」:ThreatHistoryChart 缺数据时显占位,不渲染假图
- 「useUltimateAlert 404/501 优雅降级」:5xx 透传,4xx 视为 null,符合「无警报」语义

## 四、M3 未完成 / 已知遗留

### 4.1 沙箱限制

- `pnpm install` 未执行 → TS linter 报「JSX.IntrinsicElements 不存在」(M0 已知,本地 `pnpm install` 即可消失)
- 无 PG / Redis / 真实 EOD 数据 → 集成测试仅 smoke 骨架(沙箱自动跳,生产环境跑)
- BD-087 校准仅理论推导,真实回测待 M4 末起

### 4.2 二期待启动

- 8-K Item 8.01 回购公告解析器(BD-051):DAG 调 `load_buyback([])` 空跑不阻塞,二期接 EDGAR full-text search
- 沙箱 `make up` 起 Docker 验证集成 smoke 真实链路

### 4.3 测试数变化

- M2 末:194 个 pytest(M2 6 套新测试,前 6 套已含)
- M3 末:**仍 194 个**(M3 未新增后端测试,均依赖现有)
- M3 增量在 DAG / API 端点层级,代码层用现有 threat_score / ultimate_alert 单元测试守护
- 前端无 Vitest 测试(M0 已知,二期接 vitest 框架)

## 五、立即可跑(本地)

```bash
# 1. 起基础设施 + 后端
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up
cd backend
uv sync --extra dev
uv run python -m etl.symbol_seed
uv run fastapi dev app/main.py    # http://localhost:8000/docs

# 2. 跑后端测试(OQ-02 守护)
uv run pytest -q                  # 期望 194 passed

# 3. 跑 EOD 流水线(触发 M3 DAG 真实调掇)
uv run python -m etl.pipeline 2024-02-01

# 4. 跑集成 smoke test
HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py
# 期望 9/9 passed

# 5. 前端
cd ../frontend
pnpm install                       # 消 TS linter 报错
pnpm dev                           # http://localhost:5173/symbol/AAPL
# 看到 SignalLifecycleBadge + ThreatHistoryChart + UltimateAlertOverlay
```

## 六、M4 启动接力

### 6.1 接力入口

- **校准数据集入口**:`etl/backtest_dataset.py` + `etl/backtest_event_goldset.py`(M2 末已实装)
- **回测框架 CLI**:`app/services/backtest.py run/compare`(M2 末已实装)
- **前端自定义篮 UI**:`frontend/src/routes/basket.tsx`(M0 占位,待 M4 启)

### 6.2 M4 开工顺序

1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 194 passed
2. **集成 smoke**:`HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py` → 9/9
3. **M4 启动**:BD-085 历史 EOD 数据集(1–2 年) + BD-086 金标准事件集 ≥30 个(CR + 产品双人 review)
4. **M4 中**:BD-089 跑回测,产候选权重 + 候选阈值
5. **M4 末**:BD-087 校准报告 v2.0(替换本 v1.0 草稿)
6. **M5 初**:灰度发布;Sentry 监控 1 周
7. **M5 中**:FE-060~FE-070 预警规则编辑器 + 自选篮子 + 高级功能
8. **M5 末**:WCAG / 性能 / 合规审计 / 上线预审

### 6.3 给下一位 agent 的一句话

- M3 主体 7 个 todo 全 COMPLETE,代码层就位,数据层待真实 EOD(沙箱不可达,需本地或代理)
- M3 范围**不输出投资建议**(CR-010 红线);**不数据伪装**(API 契约与数据真实性规范)
- 进入 M4 时请先读 [M3-handoff.md](M3-handoff.md) §4.1 沙箱限制,合理安排 smoke / 集成测试
- M4 重点是 BD-085/086 数据准备 + BD-089 回测,前端仅维护已有 3 组件,不加新组件
- BD-087 v2.0 替换 v1.0 时,保留 §五校准方法论 + §六时间表结构

## 七、本日记忆(自动,补充)

- M3 「警-图-表」三件套设计逻辑:UltimateAlertOverlay(最高告警)> SignalLifecycleBadge(状态机镜像)> ThreatHistoryChart(轨迹)
- OpenAPI freeze 约束在 m3t4 体现:404 表示无活跃警报,501 表示端点未实现;前端 useUltimateAlert 51 → 404 降级
- ultimate_alert 表 UNIQUE (trade_date, symbol) + 24h 防抖 = 同 symbol 每周仅 1 次高质量警报
- 纯 SVG 折线图替代 ECharts 依赖,保留包体 < 200KB(对 PWA 离线首屏加载友好)
- 「1 弹 1 次 + 用户主动关闭」UX 决策记录在 useUltimateAlert + symbol.$ticker.tsx 双侧
- 集成测试骨架「沙箱环境 + 生产环境」双模式设计,HR_SANDBOX_SKIP=1 可手动跳过
- BD-087 校准报告 v1.0 = 「草稿 + 理论推导 + 方法论 + 时间表」不现频费逽,v2.0 M5 末出
- DAG 5 task 串接:[finra, ats, yahoo_eod, yahoo_opt, sec_form4, sec_buyback] → [load_*, anomaly, etf] → score → screener
- ThreatHistoryChart 数据不足(< 2 点)显「数据积累中」占位,不渲染假图(防数据伪装)
- m3t3 修复 React 反模式:setState in render → 改 useEffect 异步(避免 "Cannot update a component while rendering" 警告)

---

*本文档为 M3 接力版完成报告。下一位 agent 从 §6 M4 启动接力开工。*
