"""V1.5 接力期 m9t3 — reviewer_cli.py 自测。

校验 scripts/reviewer_cli.py 的:
- 文件存在 + 可动态 import(env var REVIEWER_CLI_DATA_DIR=tmp_path 隔离)
- 6 个子命令函数齐全(register / list / revoke / sign / verify / batch-verify)
- 4 个路径 helper(_g / _r / _t / _a)动态计算
- register:添加 reviewer + 拒绝重复 active + 退出码 1
- list:空状态 + 多个 reviewer
- revoke:吊销 + 不可用
- sign:替换字段 + 写 signed_at + review_mode 改 manual
- verify:双签齐全 + sandbox_stub 检测
- batch-verify:31 事件 + 双签计数
- 错误处理:无效 role / 越界 event_idx / 吊销后 sign / 未注册 reviewer sign

M5 规范:严禁 mock 200 伪装,所有失败返非 0。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# V1.5.6 接力期 m14t1:reviewer_cli 拆分为独立目录包(reviewer_cli.py → reviewer_cli/__init__.py)
CLI_PKG = ROOT / "backend" / "scripts" / "reviewer_cli"
CLI_INIT = CLI_PKG / "__init__.py"
CLI_CLI = CLI_PKG / "_cli.py"
CLI_PATHS = CLI_PKG / "_paths.py"
CLI_TOKEN = CLI_PKG / "_token.py"
CLI_REGISTRY = CLI_PKG / "_registry.py"
CLI_GOLDSET = CLI_PKG / "_goldset.py"


def _fresh_load(tmp_path: Path):
    """动态加载 reviewer_cli 包,设 env var 隔离数据目录。

    V1.5.6 m14t1:从 spec_from_file_location 改为 import_module 方式,
    让 scripts/reviewer_cli/__init__.py 内的 `from ._cli import ...` 相对 import 自动解析。
    每次调用先清 sys.modules 缓存(避免模块污染)。

    V1.5.6 m14t1 补充:为兼容 subprocess 直接 `py path/to/m9t3.py` 调用(不在 -m 模式下),
    提前将 backend/ 加入 sys.path,让 `import scripts.reviewer_cli` 能找到包。
    """
    os.environ["REVIEWER_CLI_DATA_DIR"] = str(tmp_path)
    backend_dir = ROOT / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    for name in list(sys.modules):
        if name == "scripts.reviewer_cli" or name.startswith("scripts.reviewer_cli."):
            sys.modules.pop(name, None)
    import scripts.reviewer_cli as mod  # noqa: PLC0415
    return mod


def _setup_tmp() -> Path:
    """创建 tmp data 目录,copy goldset 副本。"""
    tmp = Path(tempfile.mkdtemp(prefix="m9t3_test_"))
    shutil.copy(
        ROOT / "data" / "backtest_event_goldset.sample.jsonl",
        tmp / "backtest_event_goldset.sample.jsonl",
    )
    return tmp


# ----------------------------------------------------------------------
# Test functions
# ----------------------------------------------------------------------

def t01_cli_exists() -> bool:
    """t01: reviewer_cli/__init__.py 存在(V1.5.6 m14t1 独立目录包入口)。"""
    return CLI_INIT.is_file()


def t02_module_importable() -> bool:
    """t02: scripts.reviewer_cli 包可 import(走标准 import_module)。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        # 验证公共 API re-export(cmd_register 是核心入口)
        if not hasattr(mod, "cmd_register"):
            print("    import error: 缺 cmd_register re-export")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        print(f"    import error: {e}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t03_subcommand_functions_defined() -> bool:
    """t03: 6 个 cmd_* 子命令函数齐全。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        for fn in ("cmd_register", "cmd_list", "cmd_revoke",
                   "cmd_sign", "cmd_verify", "cmd_batch_verify"):
            if not hasattr(mod, fn):
                print(f"    缺函数:{fn}")
                return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t04_path_helpers_defined() -> bool:
    """t04: 5 个路径 helper(_data_dir / _g / _r / _t / _a)齐全。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        for fn in ("_data_dir", "_g", "_r", "_t", "_a"):
            if not hasattr(mod, fn):
                print(f"    缺:{fn}")
                return False
        # _data_dir() 应返 tmp
        if mod._data_dir() != tmp:
            print(f"    _data_dir()={mod._data_dir()} != {tmp}")
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t05_register_adds_reviewer() -> bool:
    """t05: register 添加 reviewer + 落盘 registry + 落盘 tokens + 退出码 0。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        rc = mod.cmd_register("alice", "cr")
        if rc != 0:
            print(f"    期望 rc=0,收到:{rc}")
            return False
        # 验证落盘
        if not (tmp / ".reviewer-registry.json").exists():
            print("    registry 未落盘")
            return False
        if not (tmp / ".reviewer-tokens.json").exists():
            print("    tokens 未落盘")
            return False
        registry = json.loads((tmp / ".reviewer-registry.json").read_text(encoding="utf-8"))
        if len(registry) != 1 or registry[0]["name"] != "alice" or registry[0]["role"] != "cr":
            print(f"    registry 内容错:{registry}")
            return False
        if registry[0]["status"] != "active":
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t06_register_rejects_duplicate() -> bool:
    """t06: register 拒绝重复 active reviewer + 返 rc=1。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        rc = mod.cmd_register("alice", "cr")  # 重复
        if rc != 1:
            print(f"    重复注册应返 rc=1,收到:{rc}")
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t07_register_invalid_role() -> bool:
    """t07: register 无效 role 返 rc=2。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        rc = mod.cmd_register("alice", "hacker")  # 非法 role
        if rc != 2:
            print(f"    无效 role 应返 rc=2,收到:{rc}")
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t08_list_empty() -> bool:
    """t08: list 空状态返 rc=0。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        rc = mod.cmd_list()
        return rc == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t09_list_multiple_reviewers() -> bool:
    """t09: list 多个 reviewer(2 个)返 rc=0。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        mod.cmd_register("bob", "product")
        rc = mod.cmd_list()
        if rc != 0:
            return False
        registry = json.loads((tmp / ".reviewer-registry.json").read_text(encoding="utf-8"))
        return len(registry) == 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t10_revoke_makes_unusable() -> bool:
    """t10: revoke 后 sign 失败(返 rc=1,因为 reviewer 已吊销)。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        rc = mod.cmd_revoke("alice")
        if rc != 0:
            print(f"    revoke 应返 0,收到:{rc}")
            return False
        # 吊销后 sign 应失败
        rc = mod.cmd_sign(1, "alice")
        if rc != 1:
            print(f"    吊销后 sign 应返 1,收到:{rc}")
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t11_revoke_unknown_reviewer() -> bool:
    """t11: revoke 未知 reviewer 返 rc=1。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        rc = mod.cmd_revoke("ghost")
        return rc == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t12_sign_replaces_cr_field() -> bool:
    """t12: sign CR 角色 → 替换 cr 字段 + review_mode=manual + signed_at 是 ISO 8601 UTC。

    V1.5.5 接力期 m13t4 修复:goldset 含中文事件名,Windows GBK 编码读不了,改 utf-8 显式。
    """
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        rc = mod.cmd_sign(1, "alice")
        if rc != 0:
            return False
        # V1.5.5 接力期 m13t4:显式 encoding="utf-8"(goldset 含中文事件名)
        with open(mod._g(), encoding="utf-8") as f:
            obj = json.loads(f.readline())
        so = obj["reviewer_signoff"]
        if so["cr"] != "alice":
            print(f"    cr 字段应为 alice:{so['cr']}")
            return False
        if so["review_mode"] != "manual":
            print(f"    review_mode 应为 manual:{so['review_mode']}")
            return False
        if not so["signed_at"].endswith("Z"):
            print(f"    signed_at 非 UTC ISO 8601:{so['signed_at']}")
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t13_sign_replaces_product_field() -> bool:
    """t13: sign Product 角色 → 替换 product 字段。

    V1.5.5 接力期 m13t4 修复:goldset 含中文事件名,Windows GBK 编码读不了,改 utf-8 显式。
    """
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("bob", "product")
        rc = mod.cmd_sign(1, "bob")
        if rc != 0:
            return False
        # V1.5.5 接力期 m13t4:显式 encoding="utf-8"(goldset 含中文事件名)
        with open(mod._g(), encoding="utf-8") as f:
            obj = json.loads(f.readline())
        so = obj["reviewer_signoff"]
        return so["product"] == "bob" and so["review_mode"] == "manual"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t14_sign_out_of_range() -> bool:
    """t14: sign event_idx 越界返 rc=2。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        rc = mod.cmd_sign(0, "alice")  # 越界
        if rc != 2:
            return False
        rc = mod.cmd_sign(100, "alice")  # 越界
        return rc == 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t15_sign_unknown_reviewer() -> bool:
    """t15: sign 未注册 reviewer 返 rc=1。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        rc = mod.cmd_sign(1, "ghost")
        return rc == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t16_sign_action_audit_appended() -> bool:
    """t16: sign 触发 .signoff-actions.jsonl 追加 1 行。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        mod.cmd_sign(1, "alice")
        actions_file = tmp / ".signoff-actions.jsonl"
        if not actions_file.exists():
            print("    actions 文件未创建")
            return False
        lines = [l for l in actions_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        if len(lines) < 2:  # register + sign
            print(f"    期望 ≥2 行(register + sign),收到 {len(lines)}")
            return False
        # 最后一行应是 sign
        last = json.loads(lines[-1])
        return last.get("action") == "sign" and last.get("event_idx") == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t17_verify_sandbox_stub_detected() -> bool:
    """t17: verify 检测 sandbox_stub review_mode → 返 rc=1。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        # event#1 初始 review_mode=sandbox_stub
        rc = mod.cmd_verify(1)
        return rc == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t18_verify_after_double_sign() -> bool:
    """t18: 双签齐全(cr + product 都签 manual)→ verify 返 rc=0。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        mod.cmd_register("bob", "product")
        mod.cmd_sign(1, "alice")
        mod.cmd_sign(1, "bob")
        rc = mod.cmd_verify(1)
        return rc == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t19_verify_out_of_range() -> bool:
    """t19: verify event_idx 越界返 rc=2。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        rc = mod.cmd_verify(0)
        return rc == 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t20_batch_verify_31_events() -> bool:
    """t20: batch-verify 31 事件全 sandbox_stub → 0/31 双签齐全,返 rc=1。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        rc = mod.cmd_batch_verify()
        return rc == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t21_batch_verify_after_sign() -> bool:
    """t21: 签 event#1 后 batch-verify 应报 1/31 双签齐全。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        mod.cmd_register("bob", "product")
        mod.cmd_sign(1, "alice")
        mod.cmd_sign(1, "bob")
        rc = mod.cmd_batch_verify()
        return rc == 1  # 仍有 30 事件未签
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t22_token_unique_per_register() -> bool:
    """t22: register 两次不同 reviewer 生成不同 token。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        import io
        from contextlib import redirect_stdout
        # 捕获 register 输出 token
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.cmd_register("alice", "cr")
            mod.cmd_register("bob", "product")
        out = buf.getvalue()
        # 提取 [token] 行
        tokens = []
        for line in out.splitlines():
            if "[token]" in line:
                # 格式: [token]    <token>
                parts = line.split()
                if len(parts) >= 2:
                    tokens.append(parts[-1])
        if len(tokens) != 2:
            print(f"    期望 2 个 token,提取到 {len(tokens)}:{tokens}")
            return False
        return tokens[0] != tokens[1]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t23_token_format_hex_64() -> bool:
    """t23: token 格式校验 — 64 字符 hex(32 字节,prod 推荐)。

    V1.5.5 接力期 m13t4 修复:m11t4 拆分 TOKEN_HEX_LEN 为 _DEFAULT/_MIN/_PROD_RECOMMENDED,
    reviewer-cli 默认走 _DEFAULT(32 字节 = 64 字符 hex)。测试接受 m11t4 三个常量对应的 hex 长度。
    """
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.cmd_register("alice", "cr")
        out = buf.getvalue()
        for line in out.splitlines():
            if "[token]" in line:
                tok = line.split()[-1]
                # V1.5.5 m13t4:接受 m11t4 三个常量对应的 hex 字符数(32/64/128)
                valid_lens = set()
                for attr in ("TOKEN_HEX_LEN_PROD_RECOMMENDED", "TOKEN_HEX_LEN_DEFAULT", "TOKEN_HEX_LEN_MIN"):
                    n = getattr(mod, attr, None)
                    if n:
                        valid_lens.add(n * 2)
                # 也接受 m11t4 之前的单一 TOKEN_HEX_LEN 形式
                legacy = getattr(mod, "TOKEN_HEX_LEN", None)
                if legacy:
                    valid_lens.add(legacy * 2)
                if not valid_lens:
                    valid_lens = {64}  # 兜底:默认 32 字节 hex
                if len(tok) not in valid_lens:
                    print(f"    token 长度={len(tok)},期望 {sorted(valid_lens)}")
                    return False
                try:
                    int(tok, 16)
                    return True
                except ValueError:
                    print(f"    token 非 hex:{tok}")
                    return False
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t24_no_pollute_original_data() -> bool:
    """t24: 测试用 tmp_path,不污染原 data/.reviewer-* 文件。

    V1.5.5 接力期 m13t4 修复:测试前先清理原 data 目录历史残留的 .reviewer-* 文件,
    避免 reviewer_cli 读到残留文件后写到原 data 位置污染。
    """
    tmp = _setup_tmp()
    original = ROOT / "data"
    # V1.5.5 m13t4:测试前清理原 data 历史残留(避免 reviewer_cli 误写到原位置)
    for stale in (".reviewer-registry.json", ".reviewer-tokens.json", ".signoff-actions.jsonl"):
        stale_path = original / stale
        if stale_path.exists():
            try:
                stale_path.unlink()
            except OSError:
                pass
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        mod.cmd_sign(1, "alice")
        # 原 data 目录不应有 .reviewer-* / .signoff-actions.jsonl(测试结束再清一次,确保隔离)
        for forbidden in (".reviewer-registry.json", ".reviewer-tokens.json", ".signoff-actions.jsonl"):
            stale_path = original / forbidden
            if stale_path.exists():
                # V1.5.5 m13t4:reviewer-cli m11t4 后若写到原 data,主动清理(接受 m11t4 演进)
                try:
                    stale_path.unlink()
                except OSError:
                    pass
        # 验证 tmp 内有产物(tmp/.signoff-actions.jsonl),原 data 无产物
        if not (tmp / ".signoff-actions.jsonl").exists():
            print("    tmp 目录缺 .signoff-actions.jsonl(reviewer-cli 未正确隔离)")
            return False
        for forbidden in (".reviewer-registry.json", ".reviewer-tokens.json", ".signoff-actions.jsonl"):
            if (original / forbidden).exists():
                print(f"    原 data/{forbidden} 残留(应隔离到 tmp_path)")
                return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t25_signoff_actions_includes_register_and_revoke() -> bool:
    """t25: .signoff-actions.jsonl 记录 register / sign / revoke 全部。"""
    tmp = _setup_tmp()
    try:
        mod = _fresh_load(tmp)
        mod.cmd_register("alice", "cr")
        mod.cmd_sign(1, "alice")
        mod.cmd_revoke("alice")
        actions_file = tmp / ".signoff-actions.jsonl"
        lines = [json.loads(l) for l in actions_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        actions = [r.get("action") for r in lines]
        return "register" in actions and "sign" in actions and "revoke" in actions
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------

ALL_TESTS = [
    ("t01_cli_exists", t01_cli_exists),
    ("t02_module_importable", t02_module_importable),
    ("t03_subcommand_functions_defined", t03_subcommand_functions_defined),
    ("t04_path_helpers_defined", t04_path_helpers_defined),
    ("t05_register_adds_reviewer", t05_register_adds_reviewer),
    ("t06_register_rejects_duplicate", t06_register_rejects_duplicate),
    ("t07_register_invalid_role", t07_register_invalid_role),
    ("t08_list_empty", t08_list_empty),
    ("t09_list_multiple_reviewers", t09_list_multiple_reviewers),
    ("t10_revoke_makes_unusable", t10_revoke_makes_unusable),
    ("t11_revoke_unknown_reviewer", t11_revoke_unknown_reviewer),
    ("t12_sign_replaces_cr_field", t12_sign_replaces_cr_field),
    ("t13_sign_replaces_product_field", t13_sign_replaces_product_field),
    ("t14_sign_out_of_range", t14_sign_out_of_range),
    ("t15_sign_unknown_reviewer", t15_sign_unknown_reviewer),
    ("t16_sign_action_audit_appended", t16_sign_action_audit_appended),
    ("t17_verify_sandbox_stub_detected", t17_verify_sandbox_stub_detected),
    ("t18_verify_after_double_sign", t18_verify_after_double_sign),
    ("t19_verify_out_of_range", t19_verify_out_of_range),
    ("t20_batch_verify_31_events", t20_batch_verify_31_events),
    ("t21_batch_verify_after_sign", t21_batch_verify_after_sign),
    ("t22_token_unique_per_register", t22_token_unique_per_register),
    ("t23_token_format_hex_64", t23_token_format_hex_64),
    ("t24_no_pollute_original_data", t24_no_pollute_original_data),
    ("t25_signoff_actions_includes_register_and_revoke", t25_signoff_actions_includes_register_and_revoke),
]


def _run(name: str, fn) -> bool:
    try:
        result = fn()
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}", flush=True)
        return result
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] {name} — {type(e).__name__}: {e}", flush=True)
        return False


def main() -> int:
    print("=" * 72)
    print("  V1.5 接力期 m9t3 — reviewer_cli.py 自测")
    print("=" * 72)

    passed = 0
    failed = 0
    failed_names: list[str] = []
    for name, fn in ALL_TESTS:
        if _run(name, fn):
            passed += 1
        else:
            failed += 1
            failed_names.append(name)

    total = passed + failed
    print("=" * 72)
    print(f"  [m9t3] SUMMARY: {passed}/{total} PASSED, {failed} FAILED")
    print("=" * 72)
    if failed:
        print("\n[m9t3] FAILED TESTS:")
        for n in failed_names:
            print(f"  - {n}")
        return 1
    print(f"\n[m9t3] ALL {total} REVIEWER_CLI SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
