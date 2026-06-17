"""M10-t2 自测:ETF 真实 AP 代理数据源接入(yfinance + INAV/代理指标)。

测试范围(25 测点):
- §1 app/services/etf_proxy_real.py 文件存在 + 模块 docstring
- §2 fetch_etf_proxy_indicators async 函数存在
- §3 EtfProxyIndicators dataclass(14 字段)
- §4 PRODUCTION_REVIEW_MODE / SANDBOX_FALLBACK_REVIEW_MODE 双态常量
- §5 PROVIDER_YFINANCE / PROVIDER_SANDBOX provider 常量
- §6 ETF_PROVIDER_DEFAULT = yfinance
- §7 ARB_PREMIUM_PCT_THRESHOLD = 0.5
- §8 ARB_INAV_DEVIATION_THRESHOLD = 0.3
- §9 VOLUME_SPIKE_RATIO_THRESHOLD = 2.0
- §10 _calc_inav_deviation 函数
- §11 _calc_volume_spike 函数(5d/30d 均量 + ratio)
- §12 YFINANCE_AVAILABLE 探测(沙箱无 yfinance 也可 import)
- §13 yfinance 不可用 → fallback sandbox(reason=yfinance_unavailable)
- §14 yfinance 超时 → fallback sandbox(reason=yfinance_timeout)
- §15 yfinance 异常 → fallback sandbox(reason=yfinance_error)
- §16 yfinance 成功 → production_real(fetch_source=yfinance + sandbox=False)
- §17 强制 sandbox provider → fallback(reason=provider_sandbox)
- §18 app/api/etf.py 导入 fetch_etf_proxy_indicators(V1.5.2 双轨)
- §19 app/api/etf.py premium-discount price 参数可选(price: float | None)
- §20 app/api/etf.py 响应新增 5 字段(inav_deviation / volume_5d_avg / volume_30d_avg / volume_spike_ratio / fetch_source)
- §21 app/api/etf.py disclaimer 更新为 V1.5.2 双轨
- §22 etf_proxy_real.py 不破坏 etf_proxy.py(m9t5 沿用)
- §23 EtfBasket / build_etf_basket / compute_premium_discount 沿用 m9t5
- §24 不 mock 200 伪装:任何 fallback 都显式 sandbox=true + warning
- §25 语法无错(ast.parse)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP_SERVICES = BACKEND / "app" / "services"
APP_API = BACKEND / "app" / "api"

ETF_PROXY_REAL_PY = APP_SERVICES / "etf_proxy_real.py"
ETF_PROXY_PY = APP_SERVICES / "etf_proxy.py"
ETF_API_PY = APP_API / "etf.py"

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def _run(name: str, fn):
    try:
        fn()
        PASSED.append(name)
        print(f"  [PASS] {name}")
    except AssertionError as e:
        FAILED.append((name, str(e)))
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        FAILED.append((name, f"{type(e).__name__}: {e}"))
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")


# ---------- §1 etf_proxy_real.py 文件存在 + 模块 docstring ----------
def _t01_etf_proxy_real_exists_and_docstring():
    assert ETF_PROXY_REAL_PY.exists(), f"etf_proxy_real.py 应存在: {ETF_PROXY_REAL_PY}"
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "M10-t2" in text, "etf_proxy_real.py docstring 应含 M10-t2"
    assert "yfinance" in text, "etf_proxy_real.py docstring 应提 yfinance"
    assert "BD-088" in text, "etf_proxy_real.py docstring 应提 BD-088"


# ---------- §2 fetch_etf_proxy_indicators async 函数存在 ----------
def _t02_fetch_etf_proxy_indicators_exists():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "async def fetch_etf_proxy_indicators" in text, "etf_proxy_real.py 应有 async def fetch_etf_proxy_indicators"


# ---------- §3 EtfProxyIndicators dataclass ----------
def _t03_etf_proxy_indicators_dataclass():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "@dataclass" in text, "etf_proxy_real.py 应有 @dataclass"
    assert "class EtfProxyIndicators" in text, "etf_proxy_real.py 应有 EtfProxyIndicators class"
    for field_name in ("etf_ticker", "market_price", "nav", "inav", "premium", "premium_pct",
                       "inav_deviation", "volume_5d_avg", "volume_30d_avg", "volume_spike_ratio",
                       "arb_opportunity", "fetched_at", "fetch_source", "review_mode", "sandbox"):
        assert field_name in text, f"EtfProxyIndicators 应含 {field_name}"


# ---------- §4 PRODUCTION_REVIEW_MODE / SANDBOX_FALLBACK_REVIEW_MODE 双态常量 ----------
def _t04_dual_review_mode_constants():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert 'PRODUCTION_REVIEW_MODE = "production_real"' in text, "etf_proxy_real.py 应有 PRODUCTION_REVIEW_MODE='production_real'"
    assert 'SANDBOX_FALLBACK_REVIEW_MODE = "sandbox_stub_v15_prep"' in text, "etf_proxy_real.py 应有 SANDBOX_FALLBACK_REVIEW_MODE='sandbox_stub_v15_prep'"


# ---------- §5 PROVIDER_YFINANCE / PROVIDER_SANDBOX ----------
def _t05_provider_constants():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert 'PROVIDER_YFINANCE = "yfinance"' in text, "etf_proxy_real.py 应有 PROVIDER_YFINANCE='yfinance'"
    assert 'PROVIDER_SANDBOX = "sandbox"' in text, "etf_proxy_real.py 应有 PROVIDER_SANDBOX='sandbox'"


# ---------- §6 ETF_PROVIDER_DEFAULT = yfinance ----------
def _t06_etf_provider_default():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "ETF_PROVIDER_DEFAULT = PROVIDER_YFINANCE" in text, "etf_proxy_real.py 应 ETF_PROVIDER_DEFAULT=PROVIDER_YFINANCE"


# ---------- §7 ARB_PREMIUM_PCT_THRESHOLD = 0.5 ----------
def _t07_arb_premium_pct_threshold():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "ARB_PREMIUM_PCT_THRESHOLD = 0.5" in text, "etf_proxy_real.py 应 ARB_PREMIUM_PCT_THRESHOLD=0.5(|premium_pct| > 0.5%)"


# ---------- §8 ARB_INAV_DEVIATION_THRESHOLD = 0.3 ----------
def _t08_arb_inav_deviation_threshold():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "ARB_INAV_DEVIATION_THRESHOLD = 0.3" in text, "etf_proxy_real.py 应 ARB_INAV_DEVIATION_THRESHOLD=0.3"


# ---------- §9 VOLUME_SPIKE_RATIO_THRESHOLD = 2.0 ----------
def _t09_volume_spike_ratio_threshold():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "VOLUME_SPIKE_RATIO_THRESHOLD = 2.0" in text, "etf_proxy_real.py 应 VOLUME_SPIKE_RATIO_THRESHOLD=2.0(5d/30d > 2x)"


# ---------- §10 _calc_inav_deviation 函数 ----------
def _t10_calc_inav_deviation():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "def _calc_inav_deviation" in text, "etf_proxy_real.py 应有 _calc_inav_deviation 函数"
    assert "(inav - nav) / nav * 100" in text, "_calc_inav_deviation 应计算 (inav-nav)/nav*100"


# ---------- §11 _calc_volume_spike 函数 ----------
def _t11_calc_volume_spike():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "def _calc_volume_spike" in text, "etf_proxy_real.py 应有 _calc_volume_spike 函数"
    assert "statistics.mean" in text, "_calc_volume_spike 应使用 statistics.mean"
    assert "avg_5d / avg_30d" in text or "avg_5d/avg_30d" in text, "_calc_volume_spike 应计算 ratio"


# ---------- §12 YFINANCE_AVAILABLE 探测 ----------
def _t12_yfinance_available_probe():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "import yfinance" in text, "etf_proxy_real.py 应 import yfinance"
    assert "YFINANCE_AVAILABLE" in text, "etf_proxy_real.py 应探测 YFINANCE_AVAILABLE"
    assert "except ImportError" in text, "etf_proxy_real.py 应 try/except ImportError 探测 yfinance"


# ---------- §13 yfinance 不可用 → fallback sandbox ----------
def _t13_yfinance_unavailable_fallback():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "if provider == PROVIDER_SANDBOX or not YFINANCE_AVAILABLE:" in text, "yfinance 不可用应分支判定"
    assert '"yfinance_unavailable"' in text, "yfinance 不可用应标 reason=yfinance_unavailable"


# ---------- §14 yfinance 超时 → fallback sandbox ----------
def _t14_yfinance_timeout_fallback():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "asyncio.TimeoutError" in text or "asyncio.wait_for" in text, "etf_proxy_real.py 应有 asyncio.wait_for 超时机制"
    assert '"yfinance_timeout"' in text, "yfinance 超时应标 reason=yfinance_timeout"


# ---------- §15 yfinance 异常 → fallback sandbox ----------
def _t15_yfinance_error_fallback():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert '"yfinance_error"' in text, "yfinance 异常应标 reason=yfinance_error"
    assert "except Exception as e" in text, "etf_proxy_real.py 应兜底 Exception 异常"


# ---------- §16 yfinance 成功 → production_real ----------
def _t16_yfinance_success_production_real():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert 'fetch_source=PROVIDER_YFINANCE' in text, "yfinance 成功应标 fetch_source=yfinance"
    assert 'review_mode=PRODUCTION_REVIEW_MODE' in text, "yfinance 成功应标 review_mode=production_real"
    assert "sandbox=False" in text, "yfinance 成功应标 sandbox=False"


# ---------- §17 强制 sandbox provider → fallback ----------
def _t17_provider_sandbox_fallback():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    assert "provider == PROVIDER_SANDBOX" in text, "强制 sandbox provider 应分支判定"
    assert '"provider_sandbox"' in text, "强制 sandbox 应标 reason=provider_sandbox"


# ---------- §18 app/api/etf.py 导入 fetch_etf_proxy_indicators ----------
def _t18_api_etf_imports_real():
    text = ETF_API_PY.read_text(encoding="utf-8")
    assert "from app.services.etf_proxy_real import" in text, "app/api/etf.py 应 import etf_proxy_real"
    assert "fetch_etf_proxy_indicators" in text, "app/api/etf.py 应导入 fetch_etf_proxy_indicators"
    assert "PRODUCTION_REVIEW_MODE" in text, "app/api/etf.py 应导入 PRODUCTION_REVIEW_MODE"


# ---------- §19 app/api/etf.py premium-discount price 参数可选 ----------
def _t19_api_etf_price_optional():
    text = ETF_API_PY.read_text(encoding="utf-8")
    # price 从必填改可选
    assert "price: float | None" in text, "app/api/etf.py premium-discount price 参数应可选(price: float | None)"
    assert "default=None" in text, "app/api/etf.py premium-discount price 默认值应=None"


# ---------- §20 app/api/etf.py 响应新增 5 字段 ----------
def _t20_api_etf_response_new_fields():
    text = ETF_API_PY.read_text(encoding="utf-8")
    for field_name in ("inav_deviation", "volume_5d_avg", "volume_30d_avg", "volume_spike_ratio", "fetch_source"):
        assert field_name in text, f"app/api/etf.py 响应应含 {field_name}"


# ---------- §21 app/api/etf.py disclaimer 更新为 V1.5.2 双轨 ----------
def _t21_api_etf_disclaimer_v152():
    text = ETF_API_PY.read_text(encoding="utf-8")
    assert "V1.5.2" in text, "app/api/etf.py disclaimer 应含 V1.5.2"
    assert "双轨" in text, "app/api/etf.py 应说明双轨"


# ---------- §22 etf_proxy_real.py 不破坏 etf_proxy.py(m9t5 沿用) ----------
def _t22_m9t5_preserved():
    text = ETF_PROXY_PY.read_text(encoding="utf-8")
    # 关键标识都还在
    for token in ("build_etf_basket", "submit_etf_order", "compute_premium_discount",
                  "EtfBasket", "EtfOrder", "SANDBOX_REVIEW_MODE"):
        assert token in text, f"etf_proxy.py 应保留 {token}(m9t5 不破坏)"


# ---------- §23 EtfBasket / build_etf_basket / compute_premium_discount 沿用 m9t5 ----------
def _t23_m9t5_symbols_reused():
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    # 沿用 m9t5 的常量 + 函数
    assert "from app.services.etf_proxy import" in text, "etf_proxy_real.py 应 from app.services.etf_proxy import"
    for token in ("SANDBOX_REVIEW_MODE", "EtfBasket", "build_etf_basket", "compute_premium_discount"):
        assert token in text, f"etf_proxy_real.py 应沿用 m9t5 {token}"


# ---------- §24 不 mock 200 伪装:任何 fallback 都显式 sandbox=true + warning ----------
def _t24_no_mock_200_explicit_fallback():
    """t24: etf_proxy_real.py 不 mock 200 伪装:显式 sandbox=True + warning 标注。

    V1.5.5 接力期 m13t5 修复:etf_proxy_real.py 演进后无 "mock 200" 字面字符串,但显式
    sandbox=True(1 处) + warning= 字段(4 处)已落地 fallback 不伪装。改为只检查
    sandbox=True + warning= 标注即可(mock 200 字面注释不强制)。
    """
    text = ETF_PROXY_REAL_PY.read_text(encoding="utf-8")
    # _build_indicators_sandbox 显式 sandbox=True
    assert text.count("sandbox=True") >= 1, "etf_proxy_real.py 应至少有 1 处显式 sandbox=True(fallback 分支)"
    # warning 必填(显示 fallback 原因)
    assert text.count("warning=") >= 3, "etf_proxy_real.py 应有 ≥3 处 warning 标注"


# ---------- §25 语法无错 ----------
def _t25_syntax_no_errors():
    for path in (ETF_PROXY_REAL_PY, ETF_API_PY):
        src = path.read_text(encoding="utf-8")
        try:
            ast.parse(src, filename=str(path))
        except SyntaxError as e:
            raise AssertionError(f"syntax error in {path.name}: {e}")


def main() -> int:
    tests = [
        ("t01_etf_proxy_real_exists_and_docstring", _t01_etf_proxy_real_exists_and_docstring),
        ("t02_fetch_etf_proxy_indicators_exists", _t02_fetch_etf_proxy_indicators_exists),
        ("t03_etf_proxy_indicators_dataclass", _t03_etf_proxy_indicators_dataclass),
        ("t04_dual_review_mode_constants", _t04_dual_review_mode_constants),
        ("t05_provider_constants", _t05_provider_constants),
        ("t06_etf_provider_default", _t06_etf_provider_default),
        ("t07_arb_premium_pct_threshold", _t07_arb_premium_pct_threshold),
        ("t08_arb_inav_deviation_threshold", _t08_arb_inav_deviation_threshold),
        ("t09_volume_spike_ratio_threshold", _t09_volume_spike_ratio_threshold),
        ("t10_calc_inav_deviation", _t10_calc_inav_deviation),
        ("t11_calc_volume_spike", _t11_calc_volume_spike),
        ("t12_yfinance_available_probe", _t12_yfinance_available_probe),
        ("t13_yfinance_unavailable_fallback", _t13_yfinance_unavailable_fallback),
        ("t14_yfinance_timeout_fallback", _t14_yfinance_timeout_fallback),
        ("t15_yfinance_error_fallback", _t15_yfinance_error_fallback),
        ("t16_yfinance_success_production_real", _t16_yfinance_success_production_real),
        ("t17_provider_sandbox_fallback", _t17_provider_sandbox_fallback),
        ("t18_api_etf_imports_real", _t18_api_etf_imports_real),
        ("t19_api_etf_price_optional", _t19_api_etf_price_optional),
        ("t20_api_etf_response_new_fields", _t20_api_etf_response_new_fields),
        ("t21_api_etf_disclaimer_v152", _t21_api_etf_disclaimer_v152),
        ("t22_m9t5_preserved", _t22_m9t5_preserved),
        ("t23_m9t5_symbols_reused", _t23_m9t5_symbols_reused),
        ("t24_no_mock_200_explicit_fallback", _t24_no_mock_200_explicit_fallback),
        ("t25_syntax_no_errors", _t25_syntax_no_errors),
    ]
    print(f"开始 m10t2 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M10-T2 ETF REAL AP PROXY TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())