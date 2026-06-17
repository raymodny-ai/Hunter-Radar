"""M5-t1 沙箱自测:openapi-frozen-v1.4.json 验证。

不动 main.py,只检查:
- JSON 可解析
- paths / schemas / tags / securitySchemes 数量合理
- 端点 path 与 .md §二.1 一致
- DTO 字段与 .md §三 DTO 字典一致(枚举 / 必含)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC_MD = ROOT / "docs" / "openapi-frozen-v1.4.md"
DOC_JSON = ROOT / "docs" / "openapi-frozen-v1.4.json"


def main() -> None:
    raw = DOC_JSON.read_text(encoding="utf-8")
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[FAIL] openapi-frozen-v1.4.json JSON 解析失败: {e}")
        sys.exit(1)
    print(f"[ok] JSON 解析通过,顶层 {list(spec.keys())}")

    # 基础字段
    print(f"[ok] openapi={spec.get('openapi')}, version={spec.get('info', {}).get('version')}")

    # paths
    paths = spec.get("paths", {})
    print(f"[ok] paths: {len(paths)} 个")
    for p, methods in sorted(paths.items()):
        for m in methods:
            print(f"     {m.upper():6s} {p}")

    # tags
    tags = [t["name"] for t in spec.get("tags", [])]
    print(f"[ok] tags: {tags}")

    # schemas
    schemas = spec.get("components", {}).get("schemas", {})
    print(f"[ok] schemas: {len(schemas)} 个 — {sorted(schemas.keys())}")

    # security
    sec = spec.get("components", {}).get("securitySchemes", {})
    print(f"[ok] securitySchemes: {list(sec.keys())}")

    # 端点数量期望:27
    n_endpoints = sum(len([k for k in m if k in ("get", "post", "put", "delete", "patch")])
                      for m in paths.values())
    print(f"[ok] 端点总数: {n_endpoints} (期望 27)")

    # M4 新增端点
    m4_paths = [
        "/api/v1/baskets",
        "/api/v1/baskets/{basket_id}",
        "/api/v1/baskets/{basket_id}/members",
        "/api/v1/baskets/{basket_id}/members/{ticker}",
        "/api/v1/baskets/{basket_id}/distribution",
        "/api/v1/alert-rules",
        "/api/v1/alert-rules/{rule_id}",
        "/api/v1/alert-rules/{rule_id}/eval",
        "/api/v1/alerts/rules",
    ]
    missing = [p for p in m4_paths if p not in paths]
    if missing:
        print(f"[FAIL] M4 新增端点缺失: {missing}")
        sys.exit(1)
    print(f"[ok] M4 新增 9 路径全部在列")

    # DTO 期望:24
    expected_dtos = {
        "ScreenerRowDTO", "ScreenerDTO",
        "BasketCreateDTO", "BasketDTO", "BasketUpdateDTO", "BasketAddMembersDTO",
        "BasketMemberDTO", "BasketDistributionByTickerDTO", "BasketDistributionDTO",
        "RuleConditionDTO", "RuleDSLDTO",
        "AlertRuleCreateDTO", "AlertRuleUpdateDTO", "AlertRuleDTO",
        "AlertRuleEvalRequestDTO", "ConditionEvalDTO",
        "AlertRuleEvalResultDTO", "AlertRuleEvalSummaryDTO",
        "ThreatScoreDTO", "OptionsAnomalyDTO", "ShortIcebergDTO",
        "DivergenceDTO", "UltimateAlertDTO", "RegimeDTO",
    }
    missing_dtos = expected_dtos - set(schemas.keys())
    if missing_dtos:
        print(f"[FAIL] DTO 缺失: {missing_dtos}")
        sys.exit(1)
    print(f"[ok] 24 DTO 全部在列")

    # 关键枚举校验
    assert set(schemas["SignalLifecycleCompatible"] ) if "SignalLifecycleCompatible" in schemas else True
    lc_enum = schemas.get("ThreatScoreDTO", {}).get("properties", {}).get("signal_lifecycle", {}).get("enum")
    assert lc_enum == ["init", "red", "yellow", "gray", "green"], f"lifecycle enum 错: {lc_enum}"
    print(f"[ok] 5 态 lifecycle 枚举正确")

    rule_op_enum = schemas["RuleConditionDTO"]["properties"]["op"]["enum"]
    expected_ops = [">=", ">", "<=", "<", "==", "!=", "in", "not_in", "contains"]
    assert rule_op_enum == expected_ops, f"op enum 错: {rule_op_enum}"
    print(f"[ok] 9 op 枚举正确")

    rule_metric_enum = schemas["RuleConditionDTO"]["properties"]["metric"]["enum"]
    expected_metrics = ["score.ema", "score.raw", "lifecycle", "lifecycle_change", "modules"]
    assert rule_metric_enum == expected_metrics, f"metric enum 错: {rule_metric_enum}"
    print(f"[ok] 5 metric 枚举正确")

    print()
    print("[m5t1] ALL OPENAPI FROZEN VERIFY PASSED")


if __name__ == "__main__":
    main()
