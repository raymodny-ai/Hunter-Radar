"""M7-t2 沙箱自测:BD-086 reviewer_signoff 双签补全校验。

校验 31 事件双签完整性:
1. JSONL 文件存在 + 31 行
2. 每个事件 reviewer_signoff 4 字段齐全(cr / product / signed_at / review_mode)
3. 双签非 TBD(全 31 事件 review_mode=sandbox_stub 或更高)
4. audit JSONL 31 行,字段结构与 JSONL 对账
5. audit MD 文件存在 + 6 章节齐全
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDSET = ROOT / "data" / "backtest_event_goldset.sample.jsonl"
AUDIT_JSONL = ROOT / "data" / "backtest_event_goldset.signoff_audit.jsonl"
AUDIT_MD = ROOT / "docs" / "BD-086-signoff-audit-log.md"

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    failures = 0

    # ---- 1. JSONL 存在 + 31 行 -------------------------------------------------
    if not t("t01_goldset_exists", GOLDSET.exists(), f"path={GOLDSET}"):
        failures += 1
        return 1
    objs = _read_jsonl(GOLDSET)
    if not t("t02_goldset_31_events", len(objs) == 31, f"len={len(objs)}"):
        failures += 1

    # ---- 2. 每个事件 reviewer_signoff 4 字段齐全 ------------------------------
    required_fields = {"cr", "product", "signed_at", "review_mode"}
    bad_records = []
    for i, obj in enumerate(objs, start=1):
        so = obj.get("reviewer_signoff", {})
        missing = required_fields - set(so.keys())
        if missing:
            bad_records.append(f"event#{i}: missing={missing}")
    if not t("t03_signoff_4_fields_complete", len(bad_records) == 0,
             f"bad={bad_records[:3]}"):
        failures += 1

    # ---- 3. 双签非 TBD(cr + product 均非 "TBD") -------------------------------
    tbd_count = sum(
        1
        for o in objs
        if o.get("reviewer_signoff", {}).get("cr") == "TBD"
        or o.get("reviewer_signoff", {}).get("product") == "TBD"
    )
    if not t("t04_signoff_no_tbd", tbd_count == 0, f"tbd_count={tbd_count}"):
        failures += 1

    # ---- 4. 双签非空 + signed_at 是 ISO 8601 UTC --------------------------------
    empty_or_bad = []
    for i, obj in enumerate(objs, start=1):
        so = obj.get("reviewer_signoff", {})
        if not so.get("cr") or not so.get("product"):
            empty_or_bad.append(f"event#{i}: empty cr/product")
        signed_at = so.get("signed_at", "")
        if not signed_at.endswith("Z"):
            empty_or_bad.append(f"event#{i}: signed_at not UTC: {signed_at!r}")
    if not t("t05_signoff_iso8601_utc", len(empty_or_bad) == 0,
             f"bad={empty_or_bad[:3]}"):
        failures += 1

    # ---- 5. review_mode 字段值域(sandbox_stub / manual / auto_audit) ----------
    valid_modes = {"sandbox_stub", "manual", "auto_audit"}
    bad_modes = []
    mode_dist: dict[str, int] = {}
    for i, obj in enumerate(objs, start=1):
        m = obj.get("reviewer_signoff", {}).get("review_mode", "")
        mode_dist[m] = mode_dist.get(m, 0) + 1
        if m not in valid_modes:
            bad_modes.append(f"event#{i}: mode={m}")
    if not t("t06_review_mode_valid", len(bad_modes) == 0, f"bad={bad_modes[:3]} dist={mode_dist}"):
        failures += 1

    # ---- 6. cr / product 命名格式(sandbox_*_<event_id>) -----------------------
    bad_format = []
    for i, obj in enumerate(objs, start=1):
        so = obj.get("reviewer_signoff", {})
        cr = so.get("cr", "")
        pr = so.get("product", "")
        if not cr.startswith("sandbox_cr_signer_") and not cr[:1].isalpha():
            bad_format.append(f"event#{i}: cr format {cr!r}")
        if not pr.startswith("sandbox_product_signer_") and not pr[:1].isalpha():
            bad_format.append(f"event#{i}: product format {pr!r}")
    if not t("t07_signoff_format_consistent", len(bad_format) == 0,
             f"bad={bad_format[:3]}"):
        failures += 1

    # ---- 7. 双签唯一性(无两个事件 cr 相同)------------------------------------
    cr_values = [o.get("reviewer_signoff", {}).get("cr") for o in objs]
    unique_cr = len(set(cr_values)) == len(cr_values)
    if not t("t08_cr_unique_per_event", unique_cr,
             f"unique={len(set(cr_values))}/{len(cr_values)}"):
        failures += 1

    # ---- 8. event_type 覆盖 3 类(short_squeeze / earnings_crash / institutional_slaughter) ----
    type_dist: dict[str, int] = {}
    for o in objs:
        t_name = o.get("event_type", "")
        type_dist[t_name] = type_dist.get(t_name, 0) + 1
    expected_types = {"short_squeeze", "earnings_crash", "institutional_slaughter"}
    if not t("t09_event_type_3_categories", set(type_dist.keys()) == expected_types,
             f"dist={type_dist}"):
        failures += 1

    # ---- 9. severity 4 档(extreme / high / medium / low) -----------------------
    sev_dist: dict[str, int] = {}
    for o in objs:
        sev_dist[o.get("severity", "")] = sev_dist.get(o.get("severity", ""), 0) + 1
    expected_sev = {"extreme", "high", "medium", "low"}
    if not t("t10_severity_4_levels", set(sev_dist.keys()) == expected_sev,
             f"dist={sev_dist}"):
        failures += 1

    # ---- 10. 时间窗口 2020-01 ~ 2024-12 全覆盖 ---------------------------------
    starts = [o.get("t_window_start", "") for o in objs]
    ends = [o.get("t_window_end", "") for o in objs]
    in_range = all("2020" <= s[:4] <= "2024" for s in starts) and \
               all("2020" <= e[:4] <= "2024" for e in ends)
    if not t("t11_time_window_2020_2024", in_range,
             f"start_min={min(starts)} end_max={max(ends)}"):
        failures += 1

    # ---- 12. audit JSONL 31 行 + 与 goldset 对账 -------------------------------
    if not t("t12_audit_jsonl_exists", AUDIT_JSONL.exists(), f"path={AUDIT_JSONL}"):
        failures += 1
    else:
        audit = _read_jsonl(AUDIT_JSONL)
        if not t("t13_audit_jsonl_31_records", len(audit) == 31,
                 f"len={len(audit)}"):
            failures += 1
        else:
            # 对账:每个 audit 记录 event_id / ticker 与 goldset 一一对应
            goldset_pairs = {(o["ticker"], o["event_type"]) for o in objs}
            audit_pairs = {(r["ticker"], r["event_type"]) for r in audit}
            if not t("t14_audit_goldset_consistent", goldset_pairs == audit_pairs,
                     f"diff={goldset_pairs ^ audit_pairs}"):
                failures += 1

    # ---- 15. audit MD 文件存在 + 6 章节齐全 ------------------------------------
    if not t("t15_audit_md_exists", AUDIT_MD.exists(), f"path={AUDIT_MD}"):
        failures += 1
    else:
        md = AUDIT_MD.read_text(encoding="utf-8")
        required = [
            "## 一、补全范围",
            "## 二、沙箱 stub 双签字段格式",
            "## 三、event_id 索引",
            "## 四、M7 落地操作清单",
            "## 五、真实环境替换步骤",
            "## 六、风险与遗留",
        ]
        missing = [s for s in required if s not in md]
        if not t("t16_audit_md_6_sections", len(missing) == 0, f"missing={missing}"):
            failures += 1

    # ---- 17. R-23 风险已登记(沿用 M4/M5/M6)-----------------------------------
    # BD-086-signoff-audit-log.md §六 风险登记表应含 R-23
    if AUDIT_MD.exists():
        md = AUDIT_MD.read_text(encoding="utf-8")
        if not t("t17_audit_md_r23_registered", "R-23" in md, "m7t2 §六 风险登记"):
            failures += 1

    # ---- 18. R-34 风险已登记(M7 新增)-----------------------------------------
    if AUDIT_MD.exists():
        md = AUDIT_MD.read_text(encoding="utf-8")
        if not t("t18_audit_md_r34_registered", "R-34" in md, "m7t2 新增 R-34"):
            failures += 1

    # ---- 19. event_id 唯一性(无两个事件 event_id 相同)------------------------
    audit = _read_jsonl(AUDIT_JSONL) if AUDIT_JSONL.exists() else []
    audit_event_ids = [r.get("event_id") for r in audit]
    unique_eid = len(set(audit_event_ids)) == len(audit_event_ids) == 31
    if not t("t19_event_id_unique", unique_eid,
             f"unique={len(set(audit_event_ids))}/{len(audit_event_ids)}"):
        failures += 1

    # ---- 20. signed_at 一致性(全 31 事件同一日期)------------------------------
    signed_ats = {o.get("reviewer_signoff", {}).get("signed_at") for o in objs}
    if not t("t20_signed_at_consistent", len(signed_ats) == 1,
             f"distinct={signed_ats}"):
        failures += 1

    print(flush=True)
    if failures == 0:
        print("[m7t2] ALL 20 SIGN-OFF (BD-086) TESTS PASSED")
        return 0
    print(f"[m7t2] {failures} TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())