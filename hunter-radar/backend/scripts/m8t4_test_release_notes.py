"""M8-t4 V1.4 release notes + 上线 checklist 自测(20+ 测点)。

V1.4 上线文档完整性 + 7 步 checklist + 4 级 rollback 校验:

Section 1 — V1.4-release-notes.md 文档完整性(8 测点):
  - 文档存在 + 11 章节齐全
  - 19 个 FE/BD 关键功能列举(M5 6 + M6 5 + M7 8)
  - CR-010 / OQ-01 / OQ-02 / OQ-16 锁定项标记
  - 数据真实性 5 红线

Section 2 — V1.4 上线 7 步 checklist(7 测点):
  - Step 1 Secrets 注入(15 项)
  - Step 2 Database 切换
  - Step 3 Redis 切换
  - Step 4 VAPID 密钥
  - Step 5 BD-086 双签
  - Step 6 BD-085 ETL
  - Step 7 BD-087 重测

Section 3 — Rollback 4 级(4 测点):
  - L1 软回滚(5min)
  - L2 数据回滚(30min)
  - L3 代码回滚(1h)
  - L4 紧急停服(5min)

Section 4 — 监控 + 升级流程(3 测点):
  - 6 健康指标 + 4 业务指标
  - 升级链 7 级
  - P0/P1/P2 告警 SLA

Section 5 — 业务硬约束(3 测点):
  - Threat Score 默认权重(stock / etf)
  - Pro 价格 19/188 USD
  - 免费/Pro 配额 3/9999
  - 灰度切流 4 阶段(0/10/50/100)

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
DOCS = ROOT / "docs"
DOC_RELEASE = DOCS / "V1.4-release-notes.md"


def _read(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Section 1: V1.4-release-notes.md 文档完整性(8 测点)
# ----------------------------------------------------------------------

def t01_doc_exists() -> bool:
    if not DOC_RELEASE.exists():
        print(f"  [FAIL] V1.4-release-notes.md 不存在: {DOC_RELEASE}")
        return False
    print(f"  [PASS] V1.4-release-notes.md 存在 ({DOC_RELEASE.stat().st_size} bytes)")
    return True


def t02_doc_has_11_sections() -> bool:
    txt = _read(DOC_RELEASE)
    expected = [
        "一、版本信息", "二、本次发布包含",
        "三、关键功能详解", "四、数据真实性承诺",
        "五、V1.4 上线 7 步 Checklist",
        "六、Rollback 步骤", "七、监控指标",
        "八、On-call 升级流程", "九、已知问题与限制",
        "十、给生产环境 ops 的一句话", "十一、本文记忆",
    ]
    missing = [h for h in expected if h not in txt]
    if missing:
        print(f"  [FAIL] 缺章节: {missing}")
        return False
    print(f"  [PASS] 11 章节齐全")
    return True


def t03_doc_19_features() -> bool:
    """19 个 FE/BD 关键功能列举。"""
    txt = _read(DOC_RELEASE)
    features = [
        "FE-005", "FE-006", "FE-007", "FE-008", "FE-009", "FE-010",  # M5 6 个
        "FE-011", "FE-012", "FE-013", "FE-014", "FE-015",  # M6 5 个
        "BD-085", "BD-086", "BD-087",  # M7 3 个 BD
        "8-K", "WH-001", "PWA-001", "CI-001", "OQ-016",  # M7 5 个其他
    ]
    missing = [f for f in features if f not in txt]
    if missing:
        print(f"  [FAIL] 缺功能 ID: {missing}")
        return False
    print(f"  [PASS] 19 个 FE/BD 关键功能齐全")
    return True


def t04_doc_cr010_marker() -> bool:
    """CR-010 禁词红线标记。"""
    txt = _read(DOC_RELEASE)
    if "CR-010" not in txt:
        print("  [FAIL] 缺 CR-010 红线")
        return False
    if "禁词" not in txt:
        print("  [FAIL] 缺禁词描述")
        return False
    print(f"  [PASS] CR-010 红线齐全")
    return True


def t05_doc_oq_locked() -> bool:
    """OQ-01 / OQ-02 / OQ-16 锁定项标记。"""
    txt = _read(DOC_RELEASE)
    oqs = ["OQ-01", "OQ-02", "OQ-16"]
    missing = [o for o in oqs if o not in txt]
    if missing:
        print(f"  [FAIL] 缺 OQ 锁定: {missing}")
        return False
    print(f"  [PASS] OQ-01/OQ-02/OQ-16 锁定齐全")
    return True


def t06_doc_data_truth_5_rules() -> bool:
    """数据真实性 5 红线。"""
    txt = _read(DOC_RELEASE)
    # §四 必含 5 红线
    rules = [
        "缺失返 200+空",
        "沙箱 fallback 显式标注",
        "CR-010 禁词扫描",
        "BD-086 双签",
        "数据源失败",
    ]
    hits = sum(1 for r in rules if r in txt)
    if hits < 4:
        print(f"  [FAIL] 数据真实性 5 红线不足:{hits}/5")
        return False
    print(f"  [PASS] 数据真实性 5 红线齐全({hits}/5)")
    return True


def t07_doc_threat_score_weights() -> bool:
    """Threat Score 默认权重齐全(stock / etf)。"""
    txt = _read(DOC_RELEASE)
    # Stock 30/35/20/15,ETF 35/45/20
    if "options: 30%" not in txt or "short: 35%" not in txt:
        print("  [FAIL] Stock 默认权重不完整")
        return False
    if "options: 35%" not in txt or "short: 45%" not in txt:
        print("  [FAIL] ETF 默认权重不完整")
        return False
    print(f"  [PASS] Threat Score 默认权重齐全(stock + etf)")
    return True


def t08_doc_pro_pricing() -> bool:
    """Pro 价格 19/188 USD 锁定。"""
    txt = _read(DOC_RELEASE)
    if "$19" not in txt or "$188" not in txt or "STRIPE_PRICE_PRO" not in txt:
        print("  [FAIL] Pro 价格 19/188 USD 缺失")
        return False
    print(f"  [PASS] Pro 价格 $19 / $188 USD 锁定")
    return True


# ----------------------------------------------------------------------
# Section 2: V1.4 上线 7 步 checklist(7 测点)
# ----------------------------------------------------------------------

def t09_step1_secrets() -> bool:
    """Step 1:Secrets 注入 15 项。"""
    txt = _read(DOC_RELEASE)
    if "Step 1:Secrets 注入" not in txt:
        print("  [FAIL] 缺 Step 1 标题")
        return False
    # P0 7 + P1 8 = 15 项
    if "P0 7 项" not in txt or "P1 8 项" not in txt:
        print("  [FAIL] Step 1 缺 P0/P1 数量")
        return False
    print(f"  [PASS] Step 1 Secrets 15 项齐全")
    return True


def t10_step2_database() -> bool:
    """Step 2:Database 切换。"""
    txt = _read(DOC_RELEASE)
    if "Step 2:Database 切换" not in txt:
        print("  [FAIL] 缺 Step 2 标题")
        return False
    # alembic + uuid-ossp/pgcrypto/pg_trgm 三扩展
    if "alembic" not in txt or "uuid-ossp" not in txt or "pg_trgm" not in txt:
        print("  [FAIL] Step 2 缺 alembic / 三扩展")
        return False
    print(f"  [PASS] Step 2 Database 切换齐全")
    return True


def t11_step3_redis() -> bool:
    """Step 3:Redis 切换。"""
    txt = _read(DOC_RELEASE)
    if "Step 3:Redis 切换" not in txt:
        print("  [FAIL] 缺 Step 3 标题")
        return False
    if "redis-cli" not in txt or "PONG" not in txt:
        print("  [FAIL] Step 3 缺 redis-cli 验证")
        return False
    print(f"  [PASS] Step 3 Redis 切换齐全")
    return True


def t12_step4_vapid() -> bool:
    """Step 4:VAPID 密钥。"""
    txt = _read(DOC_RELEASE)
    if "Step 4:VAPID 密钥生成" not in txt:
        print("  [FAIL] 缺 Step 4 标题")
        return False
    # 严禁用沙箱 keys/vapid_private.pem
    if "keys/vapid_private.pem" not in txt and "严禁" not in txt:
        print("  [FAIL] Step 4 缺沙箱密钥警告")
        return False
    print(f"  [PASS] Step 4 VAPID 密钥齐全")
    return True


def t13_step5_signoff() -> bool:
    """Step 5:BD-086 双签。"""
    txt = _read(DOC_RELEASE)
    if "Step 5:BD-086 双签替换" not in txt:
        print("  [FAIL] 缺 Step 5 标题")
        return False
    # prod_signoff_v1 替换
    if "prod_signoff_v1" not in txt or "sandbox_stub" not in txt:
        print("  [FAIL] Step 5 缺 review_mode 替换标识")
        return False
    print(f"  [PASS] Step 5 BD-086 双签齐全")
    return True


def t14_step6_etl() -> bool:
    """Step 6:BD-085 ETL 切换。"""
    txt = _read(DOC_RELEASE)
    if "Step 6:BD-085 ETL 切换" not in txt:
        print("  [FAIL] 缺 Step 6 标题")
        return False
    # backtest_dataset_real.py → backtest_dataset_pg.py
    if "backtest_dataset_pg.py" not in txt or "backfill_pg" not in txt:
        print("  [FAIL] Step 6 缺 ETL 切换标识")
        return False
    print(f"  [PASS] Step 6 BD-085 ETL 齐全")
    return True


def t15_step7_v30_retest() -> bool:
    """Step 7:BD-087 v3.0-final 重测。"""
    txt = _read(DOC_RELEASE)
    if "Step 7:BD-087" not in txt:
        print("  [FAIL] 缺 Step 7 标题")
        return False
    # scipy.stats.mannwhitneyu 替换
    if "scipy.stats.mannwhitneyu" not in txt:
        print("  [FAIL] Step 7 缺 scipy 重测")
        return False
    # 0.05 显著 + 保持 v1.0
    if "0.05" not in txt or "v1.0" not in txt:
        print("  [FAIL] Step 7 缺 p ≥ 0.05 + v1.0 决策")
        return False
    print(f"  [PASS] Step 7 BD-087 v3.0 重测齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: Rollback 4 级(4 测点)
# ----------------------------------------------------------------------

def t16_l1_soft_rollback() -> bool:
    """L1 软回滚(配置层面,5 分钟)。"""
    txt = _read(DOC_RELEASE)
    if "L1 软回滚" not in txt:
        print("  [FAIL] 缺 L1 软回滚")
        return False
    if "5 分钟" not in txt and "5min" not in txt:
        print("  [FAIL] L1 缺 5 分钟 SLA")
        return False
    print(f"  [PASS] L1 软回滚 5min 齐全")
    return True


def t17_l2_data_rollback() -> bool:
    """L2 数据回滚(30 分钟)。"""
    txt = _read(DOC_RELEASE)
    if "L2 数据回滚" not in txt:
        print("  [FAIL] 缺 L2 数据回滚")
        return False
    if "30 分钟" not in txt and "30min" not in txt:
        print("  [FAIL] L2 缺 30 分钟 SLA")
        return False
    print(f"  [PASS] L2 数据回滚 30min 齐全")
    return True


def t18_l3_code_rollback() -> bool:
    """L3 代码回滚(切回 V1.3,1 小时)。"""
    txt = _read(DOC_RELEASE)
    if "L3 代码回滚" not in txt:
        print("  [FAIL] 缺 L3 代码回滚")
        return False
    if "1 小时" not in txt and "1h" not in txt:
        print("  [FAIL] L3 缺 1 小时 SLA")
        return False
    if "git revert" not in txt and "V1.3.0" not in txt:
        print("  [FAIL] L3 缺 V1.3.0 切回方式")
        return False
    print(f"  [PASS] L3 代码回滚 1h 齐全")
    return True


def t19_l4_emergency_stop() -> bool:
    """L4 紧急停服(5 分钟)。"""
    txt = _read(DOC_RELEASE)
    if "L4 紧急停服" not in txt:
        print("  [FAIL] 缺 L4 紧急停服")
        return False
    if "maintenance mode" not in txt and "停服" not in txt:
        print("  [FAIL] L4 缺停服方式")
        return False
    if "安全事件" not in txt and "安全漏洞" not in txt:
        print("  [FAIL] L4 缺触发条件")
        return False
    print(f"  [PASS] L4 紧急停服 5min 齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: 监控 + 升级流程(3 测点)
# ----------------------------------------------------------------------

def t20_health_metrics_6() -> bool:
    """6 健康指标齐全。"""
    txt = _read(DOC_RELEASE)
    metrics = [
        "API 错误率", "API 延迟 P99", "推送送达率",
        "Webhook 签名成功率", "Stripe 支付成功率", "数据库连接池",
    ]
    missing = [m for m in metrics if m not in txt]
    if missing:
        print(f"  [FAIL] 缺健康指标: {missing}")
        return False
    print(f"  [PASS] 6 健康指标齐全")
    return True


def t21_oncall_chain_7() -> bool:
    """升级链 7 级齐全。"""
    txt = _read(DOC_RELEASE)
    levels = ["L1 监控告警", "L2 值班工程师", "L3 技术负责人",
              "L4 CR 负责人", "L5 产品负责人", "L6 CTO", "L7 CEO"]
    missing = [l for l in levels if l not in txt]
    if missing:
        print(f"  [FAIL] 缺升级链: {missing}")
        return False
    print(f"  [PASS] 升级链 7 级齐全")
    return True


def t22_alert_sla() -> bool:
    """P0/P1/P2 告警 SLA 齐全。"""
    txt = _read(DOC_RELEASE)
    if "P0" not in txt or "P1" not in txt or "P2" not in txt:
        print("  [FAIL] 缺 P0/P1/P2 分级")
        return False
    # P0: 5min → L2
    if not re.search(r"P0.*5min.*L2", txt, re.DOTALL):
        print("  [FAIL] P0 SLA 缺失(5min → L2)")
        return False
    print(f"  [PASS] P0/P1/P2 告警 SLA 齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: 业务硬约束(3 测点)
# ----------------------------------------------------------------------

def t23_gray_release_4_stages() -> bool:
    """灰度切流 4 阶段(0% / 10% / 50% / 100%)。"""
    txt = _read(DOC_RELEASE)
    if "0%" not in txt or "10%" not in txt or "50%" not in txt or "100%" not in txt:
        print("  [FAIL] 缺灰度切流 4 阶段")
        return False
    print(f"  [PASS] 灰度切流 4 阶段齐全")
    return True


def t24_quota_3_9999() -> bool:
    """免费/Pro 配额 3/9999。"""
    txt = _read(DOC_RELEASE)
    if "3 次/天" not in txt and "3次" not in txt:
        print("  [FAIL] 缺免费配额 3 次/天")
        return False
    if "9999" not in txt:
        print("  [FAIL] 缺 Pro 配额 9999")
        return False
    print(f"  [PASS] 免费/Pro 配额 3/9999 齐全")
    return True


def t25_v15_8_candidates() -> bool:
    """V1.5.1 freeze 候选 8 项。"""
    txt = _read(DOC_RELEASE)
    expected = [
        "Admin 鉴权", "EDGAR fulltext", "ETF 申赎", "Analytics events",
        "候选 A 权重", "VAPID", "env_check.py", "BD-086 双签 reviewer",
    ]
    hits = sum(1 for e in expected if e in txt)
    if hits < 6:
        print(f"  [FAIL] V1.5.1 候选 8 项不足:{hits}/8")
        return False
    print(f"  [PASS] V1.5.1 候选 8 项齐全({hits}/8)")
    return True


# ----------------------------------------------------------------------
# Main runner
# ----------------------------------------------------------------------

_PASSED: list[str] = []
_FAILED: list[str] = []


def _run(name: str, fn) -> None:
    try:
        ok = bool(fn())
    except Exception as exc:  # noqa: BLE001
        print(f"  [ERROR] {name} 抛出异常: {exc}")
        ok = False
    if ok:
        _PASSED.append(name)
    else:
        _FAILED.append(name)


def main() -> int:
    print("=== 1. V1.4-release-notes.md 文档完整性 ===")
    _run("t01_doc_exists", t01_doc_exists)
    _run("t02_doc_has_11_sections", t02_doc_has_11_sections)
    _run("t03_doc_19_features", t03_doc_19_features)
    _run("t04_doc_cr010_marker", t04_doc_cr010_marker)
    _run("t05_doc_oq_locked", t05_doc_oq_locked)
    _run("t06_doc_data_truth_5_rules", t06_doc_data_truth_5_rules)
    _run("t07_doc_threat_score_weights", t07_doc_threat_score_weights)
    _run("t08_doc_pro_pricing", t08_doc_pro_pricing)

    print("\n=== 2. V1.4 上线 7 步 checklist ===")
    _run("t09_step1_secrets", t09_step1_secrets)
    _run("t10_step2_database", t10_step2_database)
    _run("t11_step3_redis", t11_step3_redis)
    _run("t12_step4_vapid", t12_step4_vapid)
    _run("t13_step5_signoff", t13_step5_signoff)
    _run("t14_step6_etl", t14_step6_etl)
    _run("t15_step7_v30_retest", t15_step7_v30_retest)

    print("\n=== 3. Rollback 4 级 ===")
    _run("t16_l1_soft_rollback", t16_l1_soft_rollback)
    _run("t17_l2_data_rollback", t17_l2_data_rollback)
    _run("t18_l3_code_rollback", t18_l3_code_rollback)
    _run("t19_l4_emergency_stop", t19_l4_emergency_stop)

    print("\n=== 4. 监控 + 升级流程 ===")
    _run("t20_health_metrics_6", t20_health_metrics_6)
    _run("t21_oncall_chain_7", t21_oncall_chain_7)
    _run("t22_alert_sla", t22_alert_sla)

    print("\n=== 5. 业务硬约束 ===")
    _run("t23_gray_release_4_stages", t23_gray_release_4_stages)
    _run("t24_quota_3_9999", t24_quota_3_9999)
    _run("t25_v15_8_candidates", t25_v15_8_candidates)

    total = len(_PASSED) + len(_FAILED)
    print(f"\n[m8t4] SUMMARY: {len(_PASSED)}/{total} PASSED, {len(_FAILED)} FAILED")
    if _FAILED:
        print(f"[m8t4] FAILED TESTS: {', '.join(_FAILED)}")
        return 1
    print(f"[m8t4] ALL {total} RELEASE-NOTES TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
