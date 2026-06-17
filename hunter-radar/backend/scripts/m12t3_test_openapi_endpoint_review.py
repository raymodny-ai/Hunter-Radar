"""M12-t3 V1.5.4 接力期 OpenAPI 端点评审字段标注自测脚本(25 测点)。

V1.5.4 接力期 m12t3(C-5):OpenAPI 端点评审字段标注。
- 创建 docs/openapi-frozen-v1.5.4.md + .json(继承 V1.5.3,加端点 review_status)
- admin.py 4 端点 docstring 加 ### REVIEW META (V1.5.4 m12t3) 段
- endpoint_review_meta 数组:4 admin 端点显式 + 1 catch-all 描述其余 52 端点

测点结构:
- Section 1(5): V1.5.4 freeze 双文档存在
- Section 2(5): endpoint_review_meta 关键字段
- Section 3(5): admin.py 4 端点 docstring REVIEW META 段
- Section 4(5): 评审项落地 + 总脚本
- Section 5(5): 兼容性 + ONLINE-READY 校验

沙箱 stuck 走纯文本静态分析,严禁 mock 200。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SCRIPTS = ROOT / "backend" / "scripts"
BACKEND_APP_API = ROOT / "backend" / "app" / "api"
V154_MD = DOCS / "openapi-frozen-v1.5.4.md"
V154_JSON = DOCS / "openapi-frozen-v1.5.4.json"
V153_MD = DOCS / "openapi-frozen-v1.5.3.md"
ADMIN_PY = BACKEND_APP_API / "admin.py"
M8T1_PY = SCRIPTS / "m8t1_test_regression.py"

PASS = "[PASS]"
FAIL = "[FAIL]"
REVIEW_META_HEADER = "### REVIEW META (V1.5.4 m12t3)"
LAST_REVIEWED_DATE = "2026-06-15"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


# === Section 1:V1.5.4 freeze 双文档存在 ===
def test_section1_v154_docs_exist() -> tuple[int, int]:
    print("\n--- Section 1:V1.5.4 freeze 双文档存在 ---", flush=True)
    passed = failed = 0

    md_exists = V154_MD.exists()
    if t("t01_v154_md_exists", md_exists, str(V154_MD.relative_to(ROOT))):
        passed += 1
    else:
        failed += 1

    json_exists = V154_JSON.exists()
    if t("t02_v154_json_exists", json_exists, str(V154_JSON.relative_to(ROOT))):
        passed += 1
    else:
        failed += 1

    if md_exists:
        md_text = V154_MD.read_text(encoding="utf-8")
        has_title = "V1.5.4 OpenAPI Freeze" in md_text
        if t("t03_v154_md_title", has_title):
            passed += 1
        else:
            failed += 1
    else:
        t("t03_v154_md_title", False, "V1.5.4 md 不存在,跳过")
        failed += 1

    if json_exists:
        try:
            v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
            json_valid = isinstance(v154_data, dict)
            if t("t04_v154_json_valid", json_valid):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            t("t04_v154_json_valid", False, f"JSON 解析失败:{e}")
            failed += 1
            v154_data = {}
    else:
        t("t04_v154_json_valid", False, "V1.5.4 json 不存在,跳过")
        failed += 1
        v154_data = {}

    if v154_data:
        freeze_version = v154_data.get("freeze_version", "")
        if t("t05_v154_freeze_version", freeze_version == "v1.5.4",
             f"freeze_version={freeze_version}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t05_v154_freeze_version", False, "v154_data 空,跳过")
        failed += 1

    return passed, failed


# === Section 2:endpoint_review_meta 关键字段 ===
def test_section2_endpoint_review_meta() -> tuple[int, int, dict]:
    print("\n--- Section 2:endpoint_review_meta 关键字段 ---", flush=True)
    passed = failed = 0
    v154_data: dict = {}

    if not V154_JSON.exists():
        for n in ("t06", "t07", "t08", "t09", "t10"):
            t(n, False, "V1.5.4 json 不存在,跳过")
            failed += 1
        return passed, failed, v154_data

    v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
    endpoint_meta = v154_data.get("endpoint_review_meta", [])

    endpoints_total = v154_data.get("endpoints_total", 0)
    if t("t06_endpoints_total_56", endpoints_total == 56,
         f"endpoints_total={endpoints_total}"):
        passed += 1
    else:
        failed += 1

    # 4 admin 端点 + 1 catch-all = 5
    meta_len = len(endpoint_meta)
    if t("t07_endpoint_review_meta_len_5", meta_len == 5,
         f"endpoint_review_meta 长度={meta_len}"):
        passed += 1
    else:
        failed += 1

    # webhook/replay 显式条目
    webhook_entry = next(
        (e for e in endpoint_meta if e.get("endpoint") == "/api/v1/admin/webhook/replay"),
        None,
    )
    if webhook_entry and webhook_entry.get("review_status") == "passes_v154":
        if t("t08_webhook_replay_review_status_v154", True,
             "webhook/replay review_status=passes_v154"):
            passed += 1
        else:
            failed += 1
    else:
        t("t08_webhook_replay_review_status_v154", False,
          f"webhook_entry={webhook_entry}")
        failed += 1

    if webhook_entry and webhook_entry.get("m12t1_super_admin") is True:
        if t("t09_webhook_replay_super_admin", True,
             "webhook/replay m12t1_super_admin=true"):
            passed += 1
        else:
            failed += 1
    else:
        t("t09_webhook_replay_super_admin", False,
          f"webhook_entry={webhook_entry}")
        failed += 1

    if webhook_entry and webhook_entry.get("m12t3_high_risk") is True:
        if t("t10_webhook_replay_high_risk", True,
             "webhook/replay m12t3_high_risk=true"):
            passed += 1
        else:
            failed += 1
    else:
        t("t10_webhook_replay_high_risk", False,
          f"webhook_entry={webhook_entry}")
        failed += 1

    return passed, failed, v154_data


# === Section 3:admin.py 4 端点 docstring REVIEW META 段 ===
def test_section3_admin_py_docstrings() -> tuple[int, int]:
    print("\n--- Section 3:admin.py 4 端点 docstring REVIEW META 段 ---", flush=True)
    passed = failed = 0

    if not ADMIN_PY.exists():
        for n in ("t11", "t12", "t13", "t14", "t15"):
            t(n, False, f"admin.py 不存在:{ADMIN_PY}")
            failed += 1
        return passed, failed

    admin_text = ADMIN_PY.read_text(encoding="utf-8")

    # 用 def + REVIEW META 邻接关系定位
    def has_review_meta_for(func_name: str) -> bool:
        """测 func_name 函数的 docstring 内是否含 REVIEW_META_HEADER。"""
        # 定位 def(\Z 匹配字符串末尾,避免最后一个函数 lookahead 不满足)
        m = re.search(rf"async def {func_name}\b.*?(?=\n@router|\nasync def |\ndef |\Z)",
                      admin_text, re.DOTALL)
        if not m:
            return False
        func_block = m.group(0)
        return REVIEW_META_HEADER in func_block

    if t("t11_etl_run_review_meta",
         has_review_meta_for("post_etl_run"),
         "post_etl_run 含 REVIEW META 段"):
        passed += 1
    else:
        failed += 1

    if t("t12_backtest_run_review_meta",
         has_review_meta_for("post_backtest_run"),
         "post_backtest_run 含 REVIEW META 段"):
        passed += 1
    else:
        failed += 1

    if t("t13_backtest_result_review_meta",
         has_review_meta_for("get_backtest_result"),
         "get_backtest_result 含 REVIEW META 段"):
        passed += 1
    else:
        failed += 1

    if t("t14_webhook_replay_review_meta",
         has_review_meta_for("post_webhook_replay"),
         "post_webhook_replay 含 REVIEW META 段"):
        passed += 1
    else:
        failed += 1

    # 4 端点 docstring 都有 last_reviewed: 2026-06-15
    count_last_reviewed = admin_text.count(LAST_REVIEWED_DATE)
    if t("t15_four_endpoints_last_reviewed", count_last_reviewed >= 4,
         f"last_reviewed '{LAST_REVIEWED_DATE}' 出现 {count_last_reviewed} 次(预期 ≥ 4)"):
        passed += 1
    else:
        failed += 1

    return passed, failed


# === Section 4:评审项落地 + 总脚本 ===
def test_section4_review_items() -> tuple[int, int]:
    print("\n--- Section 4:评审项落地 + 总脚本 ---", flush=True)
    passed = failed = 0

    # t16:V1.5.4 md 含 C-2/C-4/C-5 评审项说明
    if V154_MD.exists():
        md_text = V154_MD.read_text(encoding="utf-8")
        c2_ok = "C-2" in md_text and "super_admin" in md_text
        c4_ok = "C-4" in md_text and "物理删除" in md_text
        c5_ok = "C-5" in md_text and "端点评审字段" in md_text
        all_three = c2_ok and c4_ok and c5_ok
        if t("t16_v154_md_c2_c4_c5_items", all_three,
             f"C-2={c2_ok} C-4={c4_ok} C-5={c5_ok}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t16_v154_md_c2_c4_c5_items", False, "V1.5.4 md 不存在")
        failed += 1

    # t17:v154_relay_tasks 3 task 都 COMPLETE
    if V154_JSON.exists():
        v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
        relay_tasks = v154_data.get("v154_relay_tasks", {})
        all_complete = all(
            task.get("status") == "COMPLETE"
            for task in relay_tasks.values()
        )
        if t("t17_v154_relay_tasks_all_complete", all_complete,
             f"3 tasks={list(relay_tasks.keys())}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t17_v154_relay_tasks_all_complete", False, "V1.5.4 json 不存在")
        failed += 1

    # t18:3 个 m12t* 脚本存在
    m12t1_exists = (SCRIPTS / "m12t1_test_super_admin_role.py").exists()
    m12t2_exists = (SCRIPTS / "m12t2_test_m7t2_deletion.py").exists()
    m12t3_exists = (SCRIPTS / "m12t3_test_openapi_endpoint_review.py").exists()
    all_three_exist = m12t1_exists and m12t2_exists and m12t3_exists
    if t("t18_three_m12_scripts_exist", all_three_exist,
         f"m12t1={m12t1_exists} m12t2={m12t2_exists} m12t3={m12t3_exists}"):
        passed += 1
    else:
        failed += 1

    # t19:75 测点总数(3 × 25)
    if V154_JSON.exists():
        v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
        total_tp = v154_data.get("v154_total_testpoints", 0)
        if t("t19_v154_total_testpoints_75", total_tp == 75,
             f"v154_total_testpoints={total_tp}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t19_v154_total_testpoints_75", False, "V1.5.4 json 不存在")
        failed += 1

    # t20:v154_total_scripts = 3
    if V154_JSON.exists():
        v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
        total_scripts = v154_data.get("v154_total_scripts", 0)
        if t("t20_v154_total_scripts_3", total_scripts == 3,
             f"v154_total_scripts={total_scripts}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t20_v154_total_scripts_3", False, "V1.5.4 json 不存在")
        failed += 1

    return passed, failed


# === Section 5:兼容性 + ONLINE-READY 校验 ===
def test_section5_online_ready() -> tuple[int, int]:
    print("\n--- Section 5:兼容性 + ONLINE-READY 校验 ---", flush=True)
    passed = failed = 0

    # t21:V1.5.3 freeze 沿用(向后兼容)
    v153_exists = V153_MD.exists()
    if t("t21_v153_freeze_kept_for_bc", v153_exists,
         f"V1.5.3 freeze 沿用:{V153_MD.relative_to(ROOT)}"):
        passed += 1
    else:
        failed += 1

    # t22:super_admin 端点列表 = 1(webhook/replay)
    if V154_JSON.exists():
        v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
        super_admin_eps = v154_data.get("super_admin_endpoints", [])
        if t("t22_super_admin_endpoints_count_1",
             len(super_admin_eps) == 1 and "/api/v1/admin/webhook/replay" in super_admin_eps,
             f"super_admin_endpoints={super_admin_eps}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t22_super_admin_endpoints_count_1", False, "V1.5.4 json 不存在")
        failed += 1

    # t23:catch-all 描述含 "52 端点"
    if V154_JSON.exists():
        v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
        endpoint_meta = v154_data.get("endpoint_review_meta", [])
        catch_all_entry = next((e for e in endpoint_meta if e.get("catch_all")), None)
        desc = catch_all_entry.get("description", "") if catch_all_entry else ""
        if t("t23_catch_all_52_endpoints", "52 端点" in desc,
             f"catch_all description={desc[:60]}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t23_catch_all_52_endpoints", False, "V1.5.4 json 不存在")
        failed += 1

    # t24:m8t1 聚合 runner 含 M12_SCRIPTS
    if M8T1_PY.exists():
        m8t1_text = M8T1_PY.read_text(encoding="utf-8")
        m12_marker = "M12_SCRIPTS" in m8t1_text
        m12t1_marker = "m12t1_test_super_admin_role.py" in m8t1_text
        m12t2_marker = "m12t2_test_m7t2_deletion.py" in m8t1_text
        m12t3_marker = "m12t3_test_openapi_endpoint_review.py" in m8t1_text
        all_m12 = m12_marker and m12t1_marker and m12t2_marker and m12t3_marker
        if t("t24_m8t1_includes_m12_scripts", all_m12,
             f"M12_SCRIPTS={m12_marker} m12t1={m12t1_marker} "
             f"m12t2={m12t2_marker} m12t3={m12t3_marker}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t24_m8t1_includes_m12_scripts", False, "m8t1 不存在")
        failed += 1

    # t25:V1.5.4 status = ONLINE-READY
    if V154_JSON.exists():
        v154_data = json.loads(V154_JSON.read_text(encoding="utf-8"))
        status = v154_data.get("status", "")
        if t("t25_v154_status_online_ready", status == "ONLINE-READY",
             f"status={status}"):
            passed += 1
        else:
            failed += 1
    else:
        t("t25_v154_status_online_ready", False, "V1.5.4 json 不存在")
        failed += 1

    return passed, failed


def main() -> int:
    print("=" * 72, flush=True)
    print("M12-t3 V1.5.4 接力期 OpenAPI 端点评审字段标注(25 测点)", flush=True)
    print("=" * 72, flush=True)

    p1, f1 = test_section1_v154_docs_exist()
    p2, f2, _ = test_section2_endpoint_review_meta()
    p3, f3 = test_section3_admin_py_docstrings()
    p4, f4 = test_section4_review_items()
    p5, f5 = test_section5_online_ready()

    total_p = p1 + p2 + p3 + p4 + p5
    total_f = f1 + f2 + f3 + f4 + f5
    total = total_p + total_f

    print("\n" + "=" * 72, flush=True)
    print(f"M12-t3 汇总:{total_p}/{total} PASS", flush=True)
    print("=" * 72, flush=True)

    if total_f > 0:
        print(f"[FAIL] {total_f} 测点失败", flush=True)
        return 1
    print("[PASS] M12-t3 V1.5.4 OpenAPI 端点评审字段标注 - 25/25 PASS", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
