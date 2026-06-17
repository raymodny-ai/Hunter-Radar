># BD-088 ETF 申赎代理 — 设计 doc (V1.5 准备)

> **状态**:🟡 V1.5 准备(M7-t9 落地,服务 stub,HTTP API 待 V1.5 freeze)
> **关联**:OpenAPI v1.5 freeze (m7t7) + V1.5 eval checklist (m7t9)
> **作者**:M7 接力 session

---

## 一、背景

ETF(Exchange-Traded Fund)申赎机制与个股交易不同:
- **申购(creation)**:交付一篮子成分股 + 现金差额 → 获得 ETF 份额(通过 AP)
- **赎回(redemption)**:交付 ETF 份额 → 获得成分股 + 现金差额(通过 AP)
- **AP(Authorized Participant)**:大型做市商(BNY Mellon / JPMorgan / Goldman Sachs)
- **现金 / 实物两种模式**:cash settlement(简单但有溢价)/ in-kind(标准但需成分股持仓)

**BD-088 业务价值**:
1. 用户可一键申赎 ETF(类似个股交易体验)
2. 自动套利机会检测(premium / discount → NAV)
3. 现金流透明(每笔申赎可追溯到成分股)

---

## 二、V1.5 范围

| 模块 | 落地层级 | V1.5 是否暴露 API |
|---|---|---|
| `app/services/etf_proxy.py` | service | ❌(仅 stub) |
| NAV/iNAV 拉取 | etl | ❌ |
| AP API 集成(下单) | service | ❌ |
| `/api/v1/etf/{ticker}/basket` | api | 🟡 V1.5.1 freeze 待定 |
| `/api/v1/etf/orders` (POST/GET) | api | 🟡 V1.5.1 freeze 待定 |
| `/api/v1/etf/orders/{order_id}` (GET) | api | 🟡 V1.5.1 freeze 待定 |

**当前 M7-t9 落地**:仅 service stub + 设计 doc,不动 OpenAPI v1.5 freeze。

---

## 三、数据模型

### 3.1 EtfBasket(申赎篮子)

```python
@dataclass
class EtfBasket:
    etf_ticker: str           # e.g., "SPY"
    nav: float                # 单位净值 USD
    inav: float               # 指示性净值(实时)
    shares_per_unit: int      # 每申购单位份数(50000 / 100000)
    cash_component: float     # 现金差额 USD
    components: list[dict]    # [{ticker, shares, weight}]
```

### 3.2 EtfOrder(申赎订单)

```python
@dataclass
class EtfOrder:
    order_id: str             # sandbox_etf_{ticker}_{timestamp}
    etf_ticker: str
    order_type: EtfOrderType  # creation | redemption
    settlement_mode: EtfSettlementMode  # cash | in_kind
    units: int                # 申购/赎回单位数
    status: EtfOrderStatus    # pending | submitted | confirmed | settled | failed | cancelled
    submitted_at: str         # ISO 8601
    settled_at: str | None
    ap: str | None            # AP 名称
    review_mode: str          # sandbox_stub_v15_prep
```

---

## 四、状态机

```
pending → submitted → confirmed → settled
   ↓          ↓           ↓
cancelled  cancelled   failed
```

| 状态 | 触发 | 备注 |
|---|---|---|
| pending | 创建订单 | 沙箱 stub 默认 |
| submitted | 调 AP API 成功 | V1.5+ |
| confirmed | AP 确认 | V1.5+ |
| settled | 结算完成 | V1.5+ |
| failed | AP 拒绝 / 校验失败 | V1.5+ |
| cancelled | 用户取消 | V1.5+ |

---

## 五、套利机会检测

`compute_premium_discount(basket, market_price)` 返:

```python
{
    "market_price": 100.50,
    "nav": 100.0,
    "premium": 0.50,
    "premium_pct": 0.5,           # 0.5%
    "arb_opportunity": True,      # |premium_pct| > 0.5% 触发套利
}
```

**业务规则**:
- `|premium_pct| > 0.5%` → 提示套利机会
- `|premium_pct| > 1.0%` → 强烈套利信号(推送通知)
- 套利方向:premium > 0 → 卖出 ETF + 买入成分股;discount > 0 → 反之

---

## 六、V1.5+ 真实落地步骤

1. **接 Bloomberg / ETF.com / 券商 API** 拉实时 NAV/iNAV
2. **AP 集成**:BNY Mellon / JPMorgan / Virtu(选 1~2 家)
3. **订单状态轮询**:cron job 每 30s 查 AP 状态 → 更新 EtfOrder.status
4. **结算跟踪**:AP settlement 文件 → ClickHouse 归档
5. **风控**:
   - 单笔 max units(防滥用)
   - 现金 settlement max notional(防误操作)
   - 用户授权:订阅 Pro+ 才能申赎
6. **OpenAPI v1.5.1 freeze**:新增 3 端点(basket / orders POST/GET / order detail)

---

## 七、风险与遗留

| ID | 风险 | 缓解 |
|---|---|---|
| **R-37**(新) | BD-088 V1.5 仅 stub,真实 AP 集成未落地 | V1.5.1 freeze 前需 Bloomberg + AP 试运行 |
| **R-38**(新) | 套利机会检测逻辑简化,实际 AP 套利含交易成本 + 市场冲击 | V1.5+ 接券商手续费 API |
| **R-39**(新) | 现金 settlement 现金流大,需风控 | V1.5+ 加单笔上限 + KYC 二次确认 |

---

## 八、本日记忆(M7-t9)

1. **BD-088 V1.5 准备落地**:`etf_proxy.py` service stub + 设计 doc
2. **不破坏 v1.5 freeze**:仅 service 层,不动 router
3. **V1.5.1 freeze 待定**:新增 3 端点(basket / orders POST-GET / order detail)
4. **R-37/38/39 风险新增**:AP 集成 + 套利成本 + 现金流风控
5. **V1.5 eval checklist**(同 m7t9 落地)登记候选 A 权重 + BD-088 + 埋点

---

> **下一步**:M7-t10(M7-handoff + V1.4 final 收尾报告)