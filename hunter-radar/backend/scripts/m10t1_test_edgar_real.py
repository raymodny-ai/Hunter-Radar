"""M10-t1 自测:EDGAR 真实 SEC API 接入(httpx → efts.sec.gov + sandbox fallback)。

测试范围(25 测点):
- §1 etl/edgar_real.py 文件存在 + 模块 docstring 含 httpx → efts.sec.gov
- §2 fetch_fulltext_sec_httpx async 函数存在
- §3 EdgarRealFetchResult dataclass(7 必填 + 2 可选字段)
- §4 PRODUCTION_REVIEW_MODE / SANDBOX_FALLBACK_REVIEW_MODE 双态常量
- §5 SEC_API_BASE_URL_DEFAULT = https://efts.sec.gov/LATEST/search-index
- §6 SEC_API_RATE_LIMIT_DEFAULT = 0.15(SEC 官方建议 ≤10 req/s)
- §7 SEC_API_TIMEOUT_DEFAULT = 15.0
- §8 _user_agent_ok 校验(无 UA / 无 @ / 长度 < 10 返 False)
- §9 _parse_sec_filing 解析 hit(过滤 form != 8-K + 抽 ticker + 抽 cik + 抽 accession + 抽 file_date)
- §10 HTTPX_AVAILABLE 探测(沙箱无 httpx 也可 import)
- §11 httpx 不可用 → fallback sandbox(reason=httpx_unavailable + warning)
- §12 无 UA → fallback sandbox(reason=user_agent_invalid + warning)
- §13 httpx 4xx-5xx → fallback sandbox(http_status 标注 + warning)
- §14 httpx 200 → production_real(fetch_source=sec_httpx + sandbox=False)
- §15 httpx TimeoutException / NetworkError → fallback sandbox(reason=httpx_error)
- §16 User-Agent 格式:SEC 强制要求含邮箱
- §17 不 mock 200 伪装:任何 fallback 都显式 sandbox=true + warning
- §18 app/api/edgar.py 导入 fetch_fulltext_sec_httpx(V1.5.2 双轨)
- §19 app/api/edgar.py 响应含 fetch_source / http_status / latency_ms / warning 4 字段
- §20 app/api/edgar.py disclaimer 更新为 V1.5.2 双轨
- §21 V1.5.2 取代 V1.5.1 的 EDGAR_API_KEY 占位(if 块删除)
- §22 edgar_real.py 不破坏 edgar_fulltext.py(m7t5 沿用)
- §23 CATEGORY_KEYWORDS / classify_summary / _KNOWN_CIK 沿用 m7t5
- §24 rate limit 0.15s 间隔(SEC 官方建议 ≤10 req/s)
- §25 语法无错(ast.parse)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ETL = BACKEND / "etl"
APP_API = BACKEND / "app" / "api"

EDGAR_REAL_PY = ETL / "edgar_real.py"
EDGAR_FULLTEXT_PY = ETL / "edgar_fulltext.py"
EDGAR_API_PY = APP_API / "edgar.py"

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


# ---------- §1 etl/edgar_real.py 文件存在 + 模块 docstring ----------
def _t01_edgar_real_exists_and_docstring():
    assert EDGAR_REAL_PY.exists(), f"etl/edgar_real.py 应存在: {EDGAR_REAL_PY}"
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "M10-t1" in text, "edgar_real.py docstring 应含 M10-t1"
    assert "httpx" in text, "edgar_real.py docstring 应提 httpx"
    assert "efts.sec.gov" in text, "edgar_real.py docstring 应提 efts.sec.gov"


# ---------- §2 fetch_fulltext_sec_httpx async 函数存在 ----------
def _t02_fetch_fulltext_sec_httpx_exists():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "async def fetch_fulltext_sec_httpx" in text, "edgar_real.py 应有 async def fetch_fulltext_sec_httpx"


# ---------- §3 EdgarRealFetchResult dataclass ----------
def _t03_edgar_real_fetch_result_dataclass():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "@dataclass" in text, "edgar_real.py 应有 @dataclass"
    assert "class EdgarRealFetchResult" in text, "edgar_real.py 应有 EdgarRealFetchResult class"
    for field_name in ("tickers_requested", "tickers_with_filings", "total_filings",
                       "filings_by_category", "fetched_at", "fetch_source", "review_mode", "sandbox"):
        assert field_name in text, f"EdgarRealFetchResult 应含 {field_name}"
    # 可选字段
    for opt in ("http_status", "latency_ms", "warning", "query_meta"):
        assert opt in text, f"EdgarRealFetchResult 应含 {opt}"


# ---------- §4 PRODUCTION_REVIEW_MODE / SANDBOX_FALLBACK_REVIEW_MODE 双态常量 ----------
def _t04_dual_review_mode_constants():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert 'PRODUCTION_REVIEW_MODE = "production_real"' in text, "edgar_real.py 应有 PRODUCTION_REVIEW_MODE='production_real'"
    assert 'SANDBOX_FALLBACK_REVIEW_MODE = "sandbox_stub"' in text, "edgar_real.py 应有 SANDBOX_FALLBACK_REVIEW_MODE='sandbox_stub'"


# ---------- §5 SEC_API_BASE_URL_DEFAULT ----------
def _t05_sec_api_base_url_default():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert 'SEC_API_BASE_URL_DEFAULT = "https://efts.sec.gov/LATEST/search-index"' in text, \
        "SEC_API_BASE_URL_DEFAULT 应=https://efts.sec.gov/LATEST/search-index"


# ---------- §6 SEC_API_RATE_LIMIT_DEFAULT = 0.15 ----------
def _t06_sec_api_rate_limit_default():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "SEC_API_RATE_LIMIT_DEFAULT = 0.15" in text, "SEC_API_RATE_LIMIT_DEFAULT 应=0.15s(SEC 官方建议 ≤10 req/s)"


# ---------- §7 SEC_API_TIMEOUT_DEFAULT = 15.0 ----------
def _t07_sec_api_timeout_default():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "SEC_API_TIMEOUT_DEFAULT = 15.0" in text, "SEC_API_TIMEOUT_DEFAULT 应=15.0s"


# ---------- §8 _user_agent_ok 校验 ----------
def _t08_user_agent_ok_validator():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "def _user_agent_ok" in text, "edgar_real.py 应有 _user_agent_ok 函数"
    # 三种返 False:无 UA / 无 @ / 长度 < 10
    assert 'if not ua:' in text, "_user_agent_ok 应校验 UA 是否为空"
    assert '"@" not in ua' in text, "_user_agent_ok 应校验 UA 是否含 @"
    assert 'len(ua) < 10' in text, "_user_agent_ok 应校验 UA 长度"


# ---------- §9 _parse_sec_filing 解析 hit ----------
def _t09_parse_sec_filing():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "def _parse_sec_filing" in text, "edgar_real.py 应有 _parse_sec_filing 函数"
    # 过滤 form != 8-K
    assert 'form != "8-K"' in text or "form != '8-K'" in text, "_parse_sec_filing 应过滤 form != 8-K"
    # 抽 ticker from _source.ticker
    assert "src.get(\"ticker\")" in text, "_parse_sec_filing 应抽 ticker"
    # 抽 cik
    assert "src.get(\"ciks\")" in text, "_parse_sec_filing 应抽 ciks"


# ---------- §10 HTTPX_AVAILABLE 探测 ----------
def _t10_httpx_available_probe():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "import httpx" in text, "edgar_real.py 应 import httpx"
    assert "HTTPX_AVAILABLE" in text, "edgar_real.py 应探测 HTTPX_AVAILABLE"
    assert "except ImportError" in text, "edgar_real.py 应 try/except ImportError 探测 httpx"


# ---------- §11 httpx 不可用 → fallback sandbox(reason=httpx_unavailable) ----------
def _t11_httpx_unavailable_fallback():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "if not HTTPX_AVAILABLE:" in text, "httpx 不可用应分支判定"
    assert '"httpx_unavailable"' in text, "httpx 不可用应标 reason=httpx_unavailable"


# ---------- §12 无 UA → fallback sandbox(reason=user_agent_invalid) ----------
def _t12_no_user_agent_fallback():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "if not _user_agent_ok(ua):" in text, "无有效 UA 应分支判定"
    assert '"user_agent_invalid"' in text, "无有效 UA 应标 reason=user_agent_invalid"


# ---------- §13 httpx 4xx-5xx → fallback sandbox(http_status 标注) ----------
def _t13_httpx_4xx_5xx_fallback():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "resp.status_code != 200" in text, "httpx 非 200 应分支判定"
    assert "http_status=resp.status_code" in text, "httpx 4xx-5xx 应保留 http_status"
    assert "SEC API 返 HTTP" in text, "httpx 4xx-5xx 应有 warning 标注 HTTP 状态"


# ---------- §14 httpx 200 → production_real ----------
def _t14_httpx_200_production_real():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert 'fetch_source="sec_httpx"' in text, "httpx 200 应标 fetch_source=sec_httpx"
    assert 'review_mode=PRODUCTION_REVIEW_MODE' in text, "httpx 200 应标 review_mode=PRODUCTION_REVIEW_MODE"
    assert "sandbox=False" in text, "httpx 200 应标 sandbox=False"


# ---------- §15 httpx TimeoutException / NetworkError → fallback sandbox ----------
def _t15_httpx_exception_fallback():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    assert "httpx.TimeoutException" in text, "edgar_real.py 应捕获 httpx.TimeoutException"
    assert "httpx.NetworkError" in text, "edgar_real.py 应捕获 httpx.NetworkError"
    assert '"httpx_error"' in text, "httpx 异常应标 reason=httpx_error"
    assert "except Exception as e" in text, "edgar_real.py 应兜底 Exception 异常"


# ---------- §16 User-Agent 格式:SEC 强制要求含邮箱 ----------
def _t16_user_agent_email_required():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    # SEC 强制 User-Agent 含邮箱(可联系)
    assert "SEC 强制要求" in text or "SEC 要求" in text, "edgar_real.py 应说明 SEC UA 强制要求"
    assert "admin@hunter-radar.example" in text or "格式" in text, "edgar_real.py 应说明 UA 格式"


# ---------- §17 不 mock 200 伪装:任何 fallback 都显式 sandbox=true + warning ----------
def _t17_no_mock_200_explicit_fallback():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    # 不允许 mock 200 伪装
    assert "不 mock 200 伪装" in text or "mock 200" in text, "edgar_real.py 应标注不 mock 200 伪装"
    # 三个 fallback 都显式 sandbox=True
    assert text.count("sandbox=True") >= 3, "edgar_real.py 应至少 3 处显式 sandbox=True(fallback 分支)"
    # warning 必填(非 None)
    assert text.count("warning=") >= 4, "edgar_real.py 应有 ≥4 处 warning 标注"


# ---------- §18 app/api/edgar.py 导入 fetch_fulltext_sec_httpx ----------
def _t18_api_edgar_imports_real():
    text = EDGAR_API_PY.read_text(encoding="utf-8")
    assert "from etl.edgar_real import" in text, "app/api/edgar.py 应 import etl.edgar_real"
    assert "fetch_fulltext_sec_httpx" in text, "app/api/edgar.py 应导入 fetch_fulltext_sec_httpx"
    assert "PRODUCTION_REVIEW_MODE" in text, "app/api/edgar.py 应导入 PRODUCTION_REVIEW_MODE"


# ---------- §19 app/api/edgar.py 响应含 4 字段 ----------
def _t19_api_edgar_response_fields():
    text = EDGAR_API_PY.read_text(encoding="utf-8")
    for field_name in ("fetch_source", "http_status", "latency_ms", "warning"):
        assert f'"{field_name}"' in text, f"app/api/edgar.py 响应应含 {field_name}"


# ---------- §20 app/api/edgar.py disclaimer 更新为 V1.5.2 双轨 ----------
def _t20_api_edgar_disclaimer_v152():
    text = EDGAR_API_PY.read_text(encoding="utf-8")
    assert "V1.5.2" in text, "app/api/edgar.py disclaimer 应含 V1.5.2"
    assert "双轨" in text or "双轨" in text.lower(), "app/api/edgar.py 应说明双轨"


# ---------- §21 V1.5.2 取代 V1.5.1 的 EDGAR_API_KEY 占位 ----------
def _t21_no_edgar_api_key_placeholder():
    """t21: app/api/edgar.py 不含 V1.5.1 的 EDGAR_API_KEY 占位代码。

    V1.5.5 接力期 m13t5 修复:L26 注释 `无 EDGAR_API_KEY 或 httpx 不可用时 → fallback sandbox`
    是 m11t2 fallback 说明,不是占位。改为检测代码层(去注释)不含 EDGAR_API_KEY = / EDGAR_API_KEY:
    """
    text = EDGAR_API_PY.read_text(encoding="utf-8")
    # 去掉注释行(以 # 开头)再检测占位代码
    code_lines = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    code_only = "\n".join(code_lines)
    # 代码层不应含 EDGAR_API_KEY 占位赋值 / os.environ.get("EDGAR_API_KEY")
    forbidden_patterns = [
        'EDGAR_API_KEY = ', 'EDGAR_API_KEY:', 'os.environ.get("EDGAR_API_KEY")',
        "os.environ.get('EDGAR_API_KEY')",
    ]
    leaked = [p for p in forbidden_patterns if p in code_only]
    assert not leaked, f"app/api/edgar.py 仍有 EDGAR_API_KEY 占位代码:{leaked}"


# ---------- §22 edgar_real.py 不破坏 edgar_fulltext.py(m7t5 沿用) ----------
def _t22_m7t5_preserved():
    text = EDGAR_FULLTEXT_PY.read_text(encoding="utf-8")
    # 关键标识都还在
    for token in ("fetch_fulltext_sandbox", "EdgarFetchResult", "CATEGORY_KEYWORDS",
                  "DEFAULT_LOOKBACK_DAYS", "SANDBOX_REVIEW_MODE"):
        assert token in text, f"edgar_fulltext.py 应保留 {token}(m7t5 不破坏)"


# ---------- §23 CATEGORY_KEYWORDS / classify_summary / _KNOWN_CIK 沿用 m7t5 ----------
def _t23_m7t5_symbols_reused():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    # 沿用 m7t5 的常量 + 函数
    assert "from etl.edgar_fulltext import" in text, "edgar_real.py 应 from etl.edgar_fulltext import"
    for token in ("CATEGORY_KEYWORDS", "DEFAULT_LOOKBACK_DAYS",
                  "EdgarFetchResult", "EdgarFiling",
                  "MAX_FILINGS_PER_TICKER", "SANDBOX_REVIEW_MODE",
                  "_KNOWN_CIK", "classify_summary", "fetch_fulltext_sandbox"):
        assert token in text, f"edgar_real.py 应沿用 m7t5 {token}"


# ---------- §24 rate limit 0.15s 间隔(SEC 官方建议 ≤10 req/s) ----------
def _t24_rate_limit_interval():
    text = EDGAR_REAL_PY.read_text(encoding="utf-8")
    # rate_limit 用 asyncio.sleep 调用
    assert "asyncio.sleep(rate_limit)" in text, "edgar_real.py 应 asyncio.sleep(rate_limit) 等待 SEC API rate limit"
    # 注释提到 SEC 官方 ≤10 req/s
    assert "10 req/s" in text or "≤10" in text, "edgar_real.py 应注释 SEC 官方 rate limit"


# ---------- §25 语法无错 ----------
def _t25_syntax_no_errors():
    for path in (EDGAR_REAL_PY, EDGAR_API_PY):
        src = path.read_text(encoding="utf-8")
        try:
            ast.parse(src, filename=str(path))
        except SyntaxError as e:
            raise AssertionError(f"syntax error in {path.name}: {e}")


def main() -> int:
    tests = [
        ("t01_edgar_real_exists_and_docstring", _t01_edgar_real_exists_and_docstring),
        ("t02_fetch_fulltext_sec_httpx_exists", _t02_fetch_fulltext_sec_httpx_exists),
        ("t03_edgar_real_fetch_result_dataclass", _t03_edgar_real_fetch_result_dataclass),
        ("t04_dual_review_mode_constants", _t04_dual_review_mode_constants),
        ("t05_sec_api_base_url_default", _t05_sec_api_base_url_default),
        ("t06_sec_api_rate_limit_default", _t06_sec_api_rate_limit_default),
        ("t07_sec_api_timeout_default", _t07_sec_api_timeout_default),
        ("t08_user_agent_ok_validator", _t08_user_agent_ok_validator),
        ("t09_parse_sec_filing", _t09_parse_sec_filing),
        ("t10_httpx_available_probe", _t10_httpx_available_probe),
        ("t11_httpx_unavailable_fallback", _t11_httpx_unavailable_fallback),
        ("t12_no_user_agent_fallback", _t12_no_user_agent_fallback),
        ("t13_httpx_4xx_5xx_fallback", _t13_httpx_4xx_5xx_fallback),
        ("t14_httpx_200_production_real", _t14_httpx_200_production_real),
        ("t15_httpx_exception_fallback", _t15_httpx_exception_fallback),
        ("t16_user_agent_email_required", _t16_user_agent_email_required),
        ("t17_no_mock_200_explicit_fallback", _t17_no_mock_200_explicit_fallback),
        ("t18_api_edgar_imports_real", _t18_api_edgar_imports_real),
        ("t19_api_edgar_response_fields", _t19_api_edgar_response_fields),
        ("t20_api_edgar_disclaimer_v152", _t20_api_edgar_disclaimer_v152),
        ("t21_no_edgar_api_key_placeholder", _t21_no_edgar_api_key_placeholder),
        ("t22_m7t5_preserved", _t22_m7t5_preserved),
        ("t23_m7t5_symbols_reused", _t23_m7t5_symbols_reused),
        ("t24_rate_limit_interval", _t24_rate_limit_interval),
        ("t25_syntax_no_errors", _t25_syntax_no_errors),
    ]
    print(f"开始 m10t1 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M10-T1 EDGAR REAL SEC API TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())