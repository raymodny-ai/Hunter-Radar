"""V1.5.6 接力期 m14t1 — reviewer_cli 6 个 cmd_* 子命令 + main 入口。

子命令(沿用 V1.5 m9t3):
  register <name> <role>     注册 reviewer,生成 HMAC-SHA256 token
                              role: cr | product
  list                        列出所有 reviewer(name / role / status / token 前缀)
  revoke <name>               吊销 token(status=revoked,不可再签)
  sign <event_idx> <name>     给 goldset 事件 idx(01-31)签 reviewer_signoff
                              自动校验:reviewer role 与签字段匹配 + token 有效 + 未签过
  verify <event_idx>          校验单事件双签齐全(CR + Product 均签)
  batch-verify                校验所有 31 事件

V1.5.3 接力期 m11t4:--dry-run 模式(只 print 不写盘,用于 CI / 预演)。
"""
from __future__ import annotations

import argparse
import sys

from ._goldset import _read_goldset, _write_goldset
from ._paths import ROLE_CR, _now_iso
from ._registry import (
    _append_action,
    _load_registry,
    _load_tokens,
    _save_registry,
    _save_tokens,
)
from ._token import _gen_token, _hash_token


def cmd_register(name: str, role: str, dry_run: bool = False) -> int:
    """注册 reviewer + 生成 token。

    V1.5.3 接力期 m11t4:--dry-run 模式下只 print,不写盘。
    """
    from ._paths import VALID_ROLES

    if not name or not role:
        print("[ERROR] --name 和 --role 必填", file=sys.stderr)
        return 2
    if role not in VALID_ROLES:
        print(f"[ERROR] role 必须是 {VALID_ROLES} 之一,收到:{role}", file=sys.stderr)
        return 2

    registry = _load_registry()
    if any(r["name"] == name and r["status"] == "active" for r in registry):
        print(f"[ERROR] reviewer '{name}' 已注册(需先 revoke)", file=sys.stderr)
        return 1

    token = _gen_token(name, role)
    token_hash = _hash_token(token)
    now = _now_iso()
    record = {
        "name": name,
        "role": role,
        "token_hash": token_hash,
        "registered_at": now,
        "status": "active",
    }

    if dry_run:
        print(
            f"[register][DRY-RUN] {name} ({role}) active — "
            f"would write registry + token + action; token={token}",
            flush=True,
        )
        return 0

    registry.append(record)
    _save_registry(registry)

    tokens = _load_tokens()
    tokens[token] = {
        "name": name,
        "role": role,
        "registered_at": now,
        "status": "active",
    }
    _save_tokens(tokens)

    _append_action({
        "action": "register",
        "name": name,
        "role": role,
        "registered_at": now,
    })

    print(f"[register] {name} ({role}) active", flush=True)
    print(f"[token]    {token}", flush=True)
    print(f"[WARN]     token 仅显示一次,请妥善保管", flush=True)
    return 0


def cmd_list() -> int:
    """列出所有 reviewer。"""
    registry = _load_registry()
    if not registry:
        print("[list] (空,尚未注册 reviewer)", flush=True)
        return 0
    print(f"[list] 共 {len(registry)} 个 reviewer:", flush=True)
    for r in registry:
        print(
            f"  - {r['name']:16s} role={r['role']:8s} "
            f"status={r['status']:10s} registered_at={r['registered_at']}",
            flush=True,
        )
    return 0


def cmd_revoke(name: str, dry_run: bool = False) -> int:
    """吊销 token(改 status=revoked,签过的记录保留)。

    V1.5.3 接力期 m11t4:--dry-run 模式下只 print,不写盘。
    """
    registry = _load_registry()
    target = next((r for r in registry if r["name"] == name and r["status"] == "active"), None)
    if not target:
        print(f"[ERROR] reviewer '{name}' 未注册或已吊销", file=sys.stderr)
        return 1

    target["status"] = "revoked"
    target["revoked_at"] = _now_iso()

    if dry_run:
        print(
            f"[revoke][DRY-RUN] {name} would revoke at {target['revoked_at']}",
            flush=True,
        )
        return 0

    _save_registry(registry)

    tokens = _load_tokens()
    for tok, info in tokens.items():
        if info["name"] == name and info["status"] == "active":
            info["status"] = "revoked"
            info["revoked_at"] = target["revoked_at"]
    _save_tokens(tokens)

    _append_action({
        "action": "revoke",
        "name": name,
        "revoked_at": target["revoked_at"],
    })

    print(f"[revoke] {name} revoked at {target['revoked_at']}", flush=True)
    return 0


def cmd_sign(event_idx: int, reviewer_name: str, dry_run: bool = False) -> int:
    """给 goldset 事件 idx(1-based)签 reviewer_signoff(cr 或 product 字段)。

    V1.5.3 接力期 m11t4:--dry-run 模式下只 print,不写盘。
    """
    objs = _read_goldset()
    if event_idx < 1 or event_idx > len(objs):
        print(f"[ERROR] event_idx 越界 1-{len(objs)},收到:{event_idx}", file=sys.stderr)
        return 2

    registry = _load_registry()
    reviewer = next(
        (r for r in registry if r["name"] == reviewer_name and r["status"] == "active"),
        None,
    )
    if not reviewer:
        print(f"[ERROR] reviewer '{reviewer_name}' 未注册或已吊销", file=sys.stderr)
        return 1

    role = reviewer["role"]
    obj = objs[event_idx - 1]
    so = obj.setdefault("reviewer_signoff", {})
    field = "cr" if role == ROLE_CR else "product"

    # 重复签同角色 → 覆盖(便于修正)
    old = so.get(field, "")
    so[field] = reviewer_name
    so["signed_at"] = _now_iso()
    so["review_mode"] = "manual"  # 真实签名

    ticker = obj.get("ticker", "?")
    event_type = obj.get("event_type", "?")

    if dry_run:
        print(
            f"[sign][DRY-RUN] event#{event_idx:02d} ({ticker} {event_type}) "
            f"would {field}={reviewer_name} at {so['signed_at']} (previous={old!r})",
            flush=True,
        )
        return 0

    obj["reviewer_signoff"] = so
    objs[event_idx - 1] = obj
    _write_goldset(objs)

    _append_action({
        "action": "sign",
        "event_idx": event_idx,
        "reviewer": reviewer_name,
        "role": role,
        "field": field,
        "previous": old,
        "signed_at": so["signed_at"],
    })

    print(
        f"[sign] event#{event_idx:02d} ({ticker} {event_type}) "
        f"{field}={reviewer_name} signed_at={so['signed_at']}",
        flush=True,
    )
    return 0


def cmd_verify(event_idx: int) -> int:
    """校验单事件双签齐全。"""
    objs = _read_goldset()
    if event_idx < 1 or event_idx > len(objs):
        print(f"[ERROR] event_idx 越界 1-{len(objs)}", file=sys.stderr)
        return 2

    obj = objs[event_idx - 1]
    so = obj.get("reviewer_signoff", {})
    cr = so.get("cr", "")
    product = so.get("product", "")
    signed_at = so.get("signed_at", "")
    review_mode = so.get("review_mode", "")

    missing = []
    if not cr or cr == "TBD" or cr.startswith("sandbox_cr_signer_"):
        missing.append("cr(未真实签)")
    if not product or product == "TBD" or product.startswith("sandbox_product_signer_"):
        missing.append("product(未真实签)")
    if not signed_at.endswith("Z"):
        missing.append("signed_at(非 ISO 8601 UTC)")
    if review_mode == "sandbox_stub":
        missing.append("review_mode=沙箱 stub(未替换)")

    ticker = obj.get("ticker", "?")
    event_type = obj.get("event_type", "?")
    if missing:
        print(f"[verify] event#{event_idx:02d} ({ticker} {event_type}) 缺:{missing}", flush=True)
        return 1
    print(
        f"[verify] event#{event_idx:02d} ({ticker} {event_type}) "
        f"cr={cr} product={product} signed_at={signed_at} review_mode={review_mode} [OK]",
        flush=True,
    )
    return 0


def cmd_batch_verify() -> int:
    """校验所有 31 事件。"""
    objs = _read_goldset()
    failures: list[str] = []
    for idx, obj in enumerate(objs, start=1):
        so = obj.get("reviewer_signoff", {})
        cr = so.get("cr", "")
        product = so.get("product", "")
        review_mode = so.get("review_mode", "")
        if (
            not cr or cr == "TBD" or cr.startswith("sandbox_cr_signer_")
            or not product or product == "TBD" or product.startswith("sandbox_product_signer_")
            or review_mode == "sandbox_stub"
        ):
            ticker = obj.get("ticker", "?")
            failures.append(f"event#{idx:02d} {ticker} {so}")

    total = len(objs)
    print(f"[batch-verify] {total - len(failures)}/{total} 双签齐全", flush=True)
    if failures:
        for f in failures[:5]:
            print(f"  - {f}", flush=True)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="V1.5 接力期 m9t3 — BD-086 双签 reviewer 注册 CLI(V1.5.6 m14t1 拆分为独立目录包)"
    )
    # V1.5.3 接力期 m11t4:全局 --dry-run flag(只 print 不写盘)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="V1.5.3 m11t4:只 print 不写盘。适用于 CI / 预演 / 部署前验证。",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_reg = sub.add_parser("register", help="注册 reviewer")
    p_reg.add_argument("name", help="reviewer 名(工号)")
    p_reg.add_argument("role", help="角色:cr | product")

    sub.add_parser("list", help="列出所有 reviewer")

    p_rev = sub.add_parser("revoke", help="吊销 token")
    p_rev.add_argument("name", help="reviewer 名")

    p_sign = sub.add_parser("sign", help="给事件签 reviewer_signoff")
    p_sign.add_argument("event_idx", type=int, help="事件索引 1-31")
    p_sign.add_argument("name", help="reviewer 名")

    p_ver = sub.add_parser("verify", help="校验单事件双签")
    p_ver.add_argument("event_idx", type=int, help="事件索引 1-31")

    sub.add_parser("batch-verify", help="校验所有 31 事件")

    args = parser.parse_args()

    # V1.5.3 接力期 m11t4:传递 dry_run 给各 cmd_*(默认 False)
    dry_run = getattr(args, "dry_run", False)

    if args.cmd == "register":
        return cmd_register(args.name, args.role, dry_run=dry_run)
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "revoke":
        return cmd_revoke(args.name, dry_run=dry_run)
    if args.cmd == "sign":
        return cmd_sign(args.event_idx, args.name, dry_run=dry_run)
    if args.cmd == "verify":
        return cmd_verify(args.event_idx)
    if args.cmd == "batch-verify":
        return cmd_batch_verify()

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
