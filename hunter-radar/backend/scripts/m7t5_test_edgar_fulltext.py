"""M7-t5 EDGAR full-text search 沙箱 stub 自测(M7 接力期)。

测试范围(22 测点):
- §1 模块加载 + 关键常量存在
- §2 CATEGORY_KEYWORDS 与 eight_k.py 一致(同步校验)
- §3 _seeded_float 同输入同输出 + 范围 [0,1)
- §4 _pick_category 分布合理(4 类都出现)
- §5 _pick_filed_offset_days 在 [0, lookback_days] 内
- §6 _pick_summary ≤200 字 + matched_keywords 非空(share-repurchase)
- §7 _make_accession 格式 CIK-YY-NNNNNN
- §8 fetch_fulltext_sandbox 返回 (result, filings) tuple
- §9 result schema:tickers_requested / total_filings / filings_by_category / sandbox / fetched_at
- §10 filings schema:ticker / cik / accession / filed_at / form / item / category / url / matched_keywords / review_mode
- §11 filings 排序:(ticker, filed_at desc)
- §12 filings category 全在 4 类合法值
- §13 filings matched_keywords 全来自对应 CATEGORY_KEYWORDS
- §14 write_jsonl + load_jsonl round-trip 一致
- §15 sandbox=True 强制 + review_mode=sandbox_stub 全 filings
- §16 deterministic:同 ticker + 同 lookback_days + 同 max_per_ticker → 同输出
- §17 max_per_ticker=1 时每 ticker 1 条
- §18 已知 CIK 命中(27 ticker 中已知)
- §19 未知 ticker 用 fallback CIK "0000000000"
- §20 27 ticker 实际产出 86 条 filing 范围(50~150)
- §21 JSONL 行数 = 1 + total_filings
- §22 classify_summary 与 eight_k.py 同步
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

EDGAR_ETL = ROOT / "backend" / "etl" / "edgar_fulltext.py"
EIGHT_K = ROOT / "backend" / "app" / "services" / "eight_k.py"
JSONL_OUT = ROOT / "data" / "edgar_8k_sandbox.jsonl"

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def _load_mod(name: str, path: Path):
    """加载 etl/app 模块并注册到 sys.modules(Python 3.14 dataclass 兼容)。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclass 需要 sys.modules[cls.__module__]
    spec.loader.exec_module(mod)
    return mod


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


# ---------- §1 模块加载 + 关键常量存在 ----------
def _t01_module_loadable():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    assert hasattr(mod, "CATEGORY_KEYWORDS"), "missing CATEGORY_KEYWORDS"
    assert hasattr(mod, "SANDBOX_REVIEW_MODE"), "missing SANDBOX_REVIEW_MODE"
    assert hasattr(mod, "_KNOWN_CIK"), "missing _KNOWN_CIK"
    assert hasattr(mod, "EdgarFiling"), "missing EdgarFiling dataclass"
    assert hasattr(mod, "EdgarFetchResult"), "missing EdgarFetchResult dataclass"
    assert hasattr(mod, "fetch_fulltext_sandbox"), "missing fetch_fulltext_sandbox"
    assert hasattr(mod, "write_jsonl"), "missing write_jsonl"
    assert hasattr(mod, "load_jsonl"), "missing load_jsonl"
    assert hasattr(mod, "classify_summary"), "missing classify_summary"


# ---------- §2 CATEGORY_KEYWORDS 与 eight_k.py 一致 ----------
def _t02_keywords_synced_with_eight_k():
    mod_edgar = _load_mod("edgar_fulltext", EDGAR_ETL)
    mod_eightk = _load_mod("eight_k", EIGHT_K)
    assert mod_edgar.CATEGORY_KEYWORDS == mod_eightk.CATEGORY_KEYWORDS, \
        f"CATEGORY_KEYWORDS 与 eight_k.py 不同步"
    assert len(mod_edgar.CATEGORY_KEYWORDS["share-repurchase"]) == 8, \
        "share-repurchase 关键词应=8"


# ---------- §3 _seeded_float 同输入同输出 + 范围 ----------
def _t03_seeded_float():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    a = mod._seeded_float("GME|0|category")
    b = mod._seeded_float("GME|0|category")
    c = mod._seeded_float("GME|1|category")
    assert a == b, "同输入应同输出"
    assert a != c, "不同输入应不同"
    assert 0.0 <= a < 1.0, f"范围 [0,1): {a}"


# ---------- §4 _pick_category 分布合理 ----------
def _t04_category_distribution():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    seen = {mod._pick_category("GME", i) for i in range(50)}
    assert "share-repurchase" in seen, "share-repurchase 应出现"
    assert "material-agreement" in seen, "material-agreement 应出现"
    assert "press-release" in seen, "press-release 应出现"


# ---------- §5 _pick_filed_offset_days 范围 ----------
def _t05_filed_offset_range():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    for i in range(20):
        d = mod._pick_filed_offset_days("AAPL", i, 180)
        assert 0 <= d < 180, f"offset 应在 [0,180): {d}"


# ---------- §6 _pick_summary ≤200 字 + matched_keywords ----------
def _t06_pick_summary():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    for cat in ("share-repurchase", "material-agreement", "press-release", "other"):
        body, matched = mod._pick_summary("AAPL", cat, 0)
        assert len(body) <= 200, f"{cat} summary 应≤200: {len(body)}"
        # matched 来自 CATEGORY_KEYWORDS(英文关键词表,sandbox body 是中文,不强求命中)
        if cat != "other":
            assert len(matched) > 0, f"{cat} matched 应非空"
            assert len(matched) <= 2, f"{cat} matched 应≤2: {len(matched)}"
            for kw in matched:
                assert kw in mod.CATEGORY_KEYWORDS[cat], f"{cat} matched '{kw}' 不在 CATEGORY_KEYWORDS"


# ---------- §7 _make_accession 格式 ----------
def _t07_accession_format():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    a = mod._make_accession("AAPL", 0, "2026-05-12T16:30:00+00:00")
    parts = a.split("-")
    assert len(parts) == 3, f"accession 应=CIK-YY-NNNNNN: {a}"
    assert parts[0].isdigit(), f"CIK 应是数字: {parts[0]}"
    assert parts[1].isdigit() and len(parts[1]) == 2, f"YY 应是 2 位数字: {parts[1]}"
    assert parts[2].isdigit() and len(parts[2]) == 6, f"序号应是 6 位数字: {parts[2]}"


# ---------- §8 fetch_fulltext_sandbox 返回 tuple ----------
def _t08_fetch_returns_tuple():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    result, filings = mod.fetch_fulltext_sandbox(["AAPL", "MSFT"], max_per_ticker=3)
    assert hasattr(result, "to_dict"), "result 应有 to_dict"
    assert isinstance(filings, list), "filings 应是 list"
    assert len(filings) > 0, "应至少 1 条 filing"


# ---------- §9 result schema ----------
def _t09_result_schema():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    result, _ = mod.fetch_fulltext_sandbox(["AAPL"])
    d = result.to_dict()
    for k in ["tickers_requested", "tickers_with_filings", "total_filings",
              "filings_by_category", "sandbox", "fetched_at"]:
        assert k in d, f"result 缺 {k}"


# ---------- §10 filings schema ----------
def _t10_filings_schema():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    _, filings = mod.fetch_fulltext_sandbox(["AAPL"], max_per_ticker=2)
    f = filings[0].to_dict()
    for k in ["ticker", "cik", "accession", "filed_at", "form", "item",
              "category", "title", "summary", "url", "matched_keywords", "review_mode"]:
        assert k in f, f"filing 缺 {k}"
    assert f["form"] == "8-K", f"form 应=8-K: {f['form']}"
    assert f["item"] == "8.01", f"item 应=8.01: {f['item']}"


# ---------- §11 filings 排序 ----------
def _t11_filings_sort():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    _, filings = mod.fetch_fulltext_sandbox(["AAPL", "MSFT", "TSLA"], max_per_ticker=3)
    for i in range(1, len(filings)):
        prev = filings[i - 1]
        cur = filings[i]
        assert prev.ticker >= cur.ticker or (prev.ticker == cur.ticker and prev.filed_at >= cur.filed_at), \
            f"排序错: {prev.ticker}/{prev.filed_at} -> {cur.ticker}/{cur.filed_at}"


# ---------- §12 filings category 合法值 ----------
def _t12_filing_category_legal():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    legal = {"share-repurchase", "material-agreement", "press-release", "other"}
    _, filings = mod.fetch_fulltext_sandbox(["AAPL", "MSFT"], max_per_ticker=3)
    for f in filings:
        assert f.category in legal, f"非法 category: {f.category}"


# ---------- §13 filings matched_keywords 合法 ----------
def _t13_matched_keywords_legal():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    _, filings = mod.fetch_fulltext_sandbox(["AAPL", "MSFT"], max_per_ticker=3)
    for f in filings:
        if f.category == "other":
            continue
        legal_kw = mod.CATEGORY_KEYWORDS[f.category]
        for kw in f.matched_keywords:
            assert kw in legal_kw, f"{f.category} 关键词 '{kw}' 不在 CATEGORY_KEYWORDS"


# ---------- §14 write_jsonl + load_jsonl round-trip ----------
def _t14_jsonl_roundtrip():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w", encoding="utf-8") as f:
        tmp = Path(f.name)
    try:
        result, filings = mod.fetch_fulltext_sandbox(["AAPL", "MSFT"], max_per_ticker=2)
        mod.write_jsonl(result, filings, tmp)
        loaded_result, loaded_filings = mod.load_jsonl(tmp)
        assert loaded_result["total_filings"] == result.total_filings
        assert len(loaded_filings) == len(filings)
        assert loaded_filings[0]["ticker"] == filings[0].ticker
    finally:
        tmp.unlink(missing_ok=True)


# ---------- §15 sandbox=True + review_mode=sandbox_stub ----------
def _t15_sandbox_markers():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    result, filings = mod.fetch_fulltext_sandbox(["AAPL", "TSLA"])
    assert result.sandbox is True
    for f in filings:
        assert f.review_mode == "sandbox_stub", f"review_mode 应=sandbox_stub: {f.review_mode}"


# ---------- §16 deterministic 同输入同输出 ----------
def _t16_deterministic():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    ref = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    r1, f1 = mod.fetch_fulltext_sandbox(["AAPL", "MSFT"], reference_date=ref)
    r2, f2 = mod.fetch_fulltext_sandbox(["AAPL", "MSFT"], reference_date=ref)
    assert r1.total_filings == r2.total_filings
    assert f1[0].accession == f2[0].accession, "同 reference_date 应同 accession"
    assert f1[0].filed_at == f2[0].filed_at


# ---------- §17 max_per_ticker=1 时每 ticker 1 条 ----------
def _t17_max_per_ticker():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    _, filings = mod.fetch_fulltext_sandbox(["AAPL", "MSFT", "TSLA"], max_per_ticker=1)
    tickers_count = {}
    for f in filings:
        tickers_count[f.ticker] = tickers_count.get(f.ticker, 0) + 1
    for t, c in tickers_count.items():
        assert c == 1, f"{t} max_per_ticker=1 应只 1 条: {c}"


# ---------- §18 已知 CIK 命中 ----------
def _t18_known_cik():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    _, filings = mod.fetch_fulltext_sandbox(["AAPL"], max_per_ticker=2)
    for f in filings:
        assert f.cik == "0000320193", f"AAPL CIK 应=0000320193: {f.cik}"


# ---------- §19 未知 ticker fallback ----------
def _t19_unknown_ticker_fallback():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    _, filings = mod.fetch_fulltext_sandbox(["UNKNOWN_TICKER_X"], max_per_ticker=1)
    assert filings[0].cik == "0000000000", f"未知 ticker 应 fallback CIK: {filings[0].cik}"


# ---------- §20 27 ticker 产出 50~150 条 ----------
def _t20_total_filings_range():
    mod = _load_mod("edgar_fulltext", EDGAR_ETL)
    tickers = sorted(mod._KNOWN_CIK.keys())
    result, _ = mod.fetch_fulltext_sandbox(tickers)
    n = len(tickers)
    assert 50 <= result.total_filings <= n * mod.MAX_FILINGS_PER_TICKER, \
        f"total_filings 应∈[50,{n * mod.MAX_FILINGS_PER_TICKER}]: {result.total_filings}"


# ---------- §21 JSONL 行数 = 1 + total_filings ----------
def _t21_jsonl_lines():
    assert JSONL_OUT.exists(), f"JSONL 产物未落: {JSONL_OUT}"
    lines = [l for l in JSONL_OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    summary = json.loads(lines[0])
    expected = 1 + summary["total_filings"]
    assert len(lines) == expected, f"JSONL 行数={len(lines)} 应={expected}"


# ---------- §22 classify_summary 与 eight_k.py 同步 ----------
def _t22_classify_summary_synced():
    mod_edgar = _load_mod("edgar_fulltext", EDGAR_ETL)
    mod_eightk = _load_mod("eight_k", EIGHT_K)
    samples = [
        "Apple 批准 share repurchase 计划",
        "Tesla material agreement 与某电池供应商",
        "NVIDIA press release 财报亮点",
        "AAPL 提交合规事项",
    ]
    for s in samples:
        assert mod_edgar.classify_summary(s) == mod_eightk.classify_summary(s), \
            f"classify 不一致: '{s}' -> edgar={mod_edgar.classify_summary(s)} vs eight_k={mod_eightk.classify_summary(s)}"


def main() -> int:
    tests = [
        ("t01_module_loadable", _t01_module_loadable),
        ("t02_keywords_synced_with_eight_k", _t02_keywords_synced_with_eight_k),
        ("t03_seeded_float", _t03_seeded_float),
        ("t04_category_distribution", _t04_category_distribution),
        ("t05_filed_offset_range", _t05_filed_offset_range),
        ("t06_pick_summary", _t06_pick_summary),
        ("t07_accession_format", _t07_accession_format),
        ("t08_fetch_returns_tuple", _t08_fetch_returns_tuple),
        ("t09_result_schema", _t09_result_schema),
        ("t10_filings_schema", _t10_filings_schema),
        ("t11_filings_sort", _t11_filings_sort),
        ("t12_filing_category_legal", _t12_filing_category_legal),
        ("t13_matched_keywords_legal", _t13_matched_keywords_legal),
        ("t14_jsonl_roundtrip", _t14_jsonl_roundtrip),
        ("t15_sandbox_markers", _t15_sandbox_markers),
        ("t16_deterministic", _t16_deterministic),
        ("t17_max_per_ticker", _t17_max_per_ticker),
        ("t18_known_cik", _t18_known_cik),
        ("t19_unknown_ticker_fallback", _t19_unknown_ticker_fallback),
        ("t20_total_filings_range", _t20_total_filings_range),
        ("t21_jsonl_lines", _t21_jsonl_lines),
        ("t22_classify_summary_synced", _t22_classify_summary_synced),
    ]
    print(f"开始 m7t5 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M7-T5 EDGAR FULLTEXT SANDBOX TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())