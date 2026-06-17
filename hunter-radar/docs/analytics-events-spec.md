># 用户增长埋点 Schema Spec — V1.5 准备

> **状态**:🟡 V1.5 准备(M7-t9 落地,service stub,HTTP API 待 V1.5.1)
> **关联**:`app/services/analytics.py` + V1.5 eval checklist
> **作者**:M7 接力 session

---

## 一、目标

1. **激活漏斗**:signup → login → screener view → basket/alert rule create → subscribe
2. **付费转化**:signup → subscribe_start → subscribe_success
3. **留存**:DAU / WAU / MAU + cohort analysis
4. **功能采用率**:每个核心功能的首次使用率 + 频次

---

## 二、事件 Schema

### 2.1 通用结构

```python
@dataclass
class AnalyticsEvent:
    event_name: str              # 事件名(下表)
    user_id_hash: str            # SHA256 哈希(避免明文 PII)
    properties: dict             # 自定义属性
    timestamp: str               # ISO 8601 UTC
    session_id: str | None       # 会话 ID
    source: Literal["web", "ios", "android"]
    review_mode: str             # sandbox_stub_v15_prep | prod
```

**PII 处理**:永远不存明文 user_id / email,统一 SHA256。

---

## 三、事件清单(V1.5 spec)

| 事件名 | 触发时机 | properties |
|---|---|---|
| `user_signup` | 注册成功 | `{ "method": "email" \| "google_oauth" }` |
| `user_login` | 登录成功 | `{ "method": "magic_link" \| "google_oauth" }` |
| `subscribe_start` | 订阅按钮点击 | `{ "plan": "pro_monthly" \| "pro_yearly" }` |
| `subscribe_success` | Stripe webhook 收到 success | `{ "plan": "...", "amount_usd": float }` |
| `subscribe_cancel` | 取消订阅 | `{ "at_period_end": bool }` |
| `screener_view` | /screener 页面加载 | `{ "filter_count": int }` |
| `basket_create` | 创建 basket | `{ "member_count": int }` |
| `alert_rule_create` | 创建 alert rule | `{ "type": "..." }` |
| `push_opt_in` | 推送授权弹窗同意 | `{ "platform": "web" \| "ios" \| "android" }` |
| `feature_flag_view` | 灰度发布 flag 检查 | `{ "flag": "...", "value": "..." }` |

---

## 四、漏斗计算

```python
def get_funnel_summary(events):
    signup = {e.user_id_hash for e in events if e.event_name == "user_signup"}
    subscribe_start = {e.user_id_hash for e in events if e.event_name == "subscribe_start"}
    subscribe_success = {e.user_id_hash for e in events if e.event_name == "subscribe_success"}
    
    return {
        "unique_users_signup": len(signup),
        "unique_users_subscribe_start": len(subscribe_start),
        "unique_users_subscribe_success": len(subscribe_success),
        "signup_to_subscribe_start": len(subscribe_start & signup) / len(signup),
        "subscribe_start_to_success": len(subscribe_success & subscribe_start) / len(subscribe_start),
    }
```

**转化率目标**:
- signup → subscribe_start: ≥ 8%
- subscribe_start → subscribe_success: ≥ 35%

---

## 五、技术架构(V1.5+)

### 5.1 沙箱 stub(M7-t9 落地)

- `app/services/analytics.py`:in-memory ring buffer(deque maxlen=1000)
- 沙箱模式下事件仅本地累计,生产环境前不发送
- `track_event()` 返 AnalyticsEvent,供业务代码调用
- `get_recent_events(n)` 调试用,读最近 N 条

### 5.2 生产环境(V1.5+)

- **前端 SDK**:postHog JS SDK 或自建 fetch
- **后端接收**:`POST /api/v1/analytics/events`(V1.5.1 freeze 新增)
- **存储**:ClickHouse(列式存储,适合事件分析)
- **报表**:Metabase / postHog 自带 dashboard

### 5.3 隐私合规

- **GDPR / CCPA**:user_id_hash 而非明文
- **数据保留**:90 天 hot + 1 年 cold archive
- **用户撤回**:删除账户 → 同步删除该用户所有 events

---

## 六、与 V1.4 既有逻辑的对接

| 现有触发点 | 改造 |
|---|---|
| `subscription.handle_webhook_event` | 收到 `customer.subscription.updated/deleted` → 调 `analytics.track_event("subscribe_success"\|"subscribe_cancel")` |
| `auth_router.login` | 登录成功 → `analytics.track_event("user_login")` |
| `auth_router.signup` | 注册成功 → `analytics.track_event("user_signup")` |
| `basket.create` | basket 创建成功 → `analytics.track_event("basket_create")` |
| `alerts.create` | alert rule 创建成功 → `analytics.track_event("alert_rule_create")` |
| `push.subscribe` | push 授权 → `analytics.track_event("push_opt_in")` |

**改造方式**:V1.5+ 集成,沙箱 stub 调用仅记录到 ring buffer,不发送。

---

## 七、风险与遗留

| ID | 风险 | 缓解 |
|---|---|---|
| **R-40**(新) | PII 脱敏可能影响用户行为分析 | V1.5+ 加 opt-in 同意弹窗(明示数据收集范围) |
| **R-41**(新) | 沙箱 in-memory ring buffer 重启丢失 | 沙箱可接受;生产用 ClickHouse |
| **R-42**(新) | 漏斗计算简化版未考虑时间窗 | V1.5+ 加 7d / 30d cohort |
| **R-43**(新) | postHog / Plausible 商业 SaaS 锁定 | 自建 ClickHouse 作为 backup |

---

## 八、本日记忆(M7-t9)

1. **analytics 服务 stub 落地**:10 个事件名 + ring buffer + funnel summary
2. **不破坏 v1.5 freeze**:仅 service 层
3. **V1.5.1 freeze 待定**:新增 `POST /api/v1/analytics/events`
4. **现有 trigger 集成清单**(§六):6 个 trigger 待 V1.5+ 集成
5. **R-40~43 风险新增**:PII / 数据保留 / cohort / SaaS 锁定

---

> **下一步**:M7-t10(M7-handoff + V1.4 final 收尾报告)