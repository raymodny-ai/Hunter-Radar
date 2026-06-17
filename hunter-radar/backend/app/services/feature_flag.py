"""BD-051/M6 灰度发布 service — 按 user_id 白名单 / 百分比放量。

数据模型(沙箱 in-memory,可被环境变量 / config 覆盖):
- FEATURE_FLAGS: flag_key → {rollout_pct: 0-100, whitelist: [user_id, ...], default: bool}
- 每个 flag 独立配置;新 flag 默认关闭

判定逻辑:
1. user_id 在 whitelist → True
2. user_id 不在 whitelist → 按 hash(flag_key + user_id) % 100 < rollout_pct → True
3. rollout_pct == 0 且 whitelist 空 → False
4. rollout_pct == 100 → True(全量)

沙箱降级:无 config 时所有 flag 用内置默认(subscribe_v2 / 8k_feed / gray_release_banner)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class FeatureFlag:
    """灰度旗标定义。"""

    rollout_pct: int = 0  # 0-100
    whitelist: tuple[str, ...] = ()
    default: bool = False
    description: str = ""


@dataclass
class FlagSnapshot:
    """某 flag 在某用户上下文下的判定结果。"""

    enabled: bool
    reason: str  # whitelist | rollout | default-off | default-on


# 内置默认 flag 集合(沙箱;生产由 settings.feature_flags 覆盖)
_DEFAULT_FLAGS: dict[str, FeatureFlag] = {
    "subscribe_v2": FeatureFlag(
        rollout_pct=10,
        whitelist=("user_smoke_001", "user_smoke_002"),
        default=False,
        description="新版订阅页 UI(M6 实验)",
    ),
    "8k_feed": FeatureFlag(
        rollout_pct=0,
        whitelist=("user_smoke_001",),
        default=False,
        description="8-K Item 8.01 重大事件流(BD-051)",
    ),
    "gray_release_banner": FeatureFlag(
        rollout_pct=100,
        whitelist=(),
        default=True,
        description="M6 灰度发布提示横幅(全员可见)",
    ),
}


# 模块级 flag 字典(沙箱)
_FLAGS: dict[str, FeatureFlag] = dict(_DEFAULT_FLAGS)


def _stable_hash(flag_key: str, user_id: str) -> int:
    """稳定 hash:同一 (flag_key, user_id) 永远落在同一桶。"""
    h = hashlib.sha256(f"{flag_key}::{user_id}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100


def list_flags() -> dict[str, FeatureFlag]:
    """列所有 flag 配置(沙箱自测用)。"""
    return dict(_FLAGS)


def register_flag(key: str, flag: FeatureFlag) -> None:
    """注册新 flag(覆盖已有同名 flag)。"""
    _FLAGS[key] = flag


def is_enabled(flag_key: str, user_id: str | None = None) -> FlagSnapshot:
    """判定某 flag 对某 user 是否启用。

    user_id 为 None(匿名访客)时:仅返 default。
    """
    flag = _FLAGS.get(flag_key)
    if flag is None:
        # 未注册的 flag 一律 False,避免误开
        return FlagSnapshot(enabled=False, reason="unknown-flag")
    if user_id is None:
        return FlagSnapshot(enabled=flag.default, reason="default-off" if not flag.default else "default-on")
    if user_id in flag.whitelist:
        return FlagSnapshot(enabled=True, reason="whitelist")
    bucket = _stable_hash(flag_key, user_id)
    if bucket < flag.rollout_pct:
        return FlagSnapshot(enabled=True, reason="rollout")
    return FlagSnapshot(enabled=flag.default, reason="default-off" if not flag.default else "default-on")


def snapshot_for_user(user_id: str, flag_keys: Iterable[str] | None = None) -> dict[str, FlagSnapshot]:
    """批量判定:给定用户 + flag 列表 → {flag_key: FlagSnapshot}。"""
    keys = list(flag_keys) if flag_keys is not None else list(_FLAGS.keys())
    return {k: is_enabled(k, user_id) for k in keys}


def reset_for_tests() -> None:
    """沙箱自测用:恢复默认 flag 集合。"""
    _FLAGS.clear()
    _FLAGS.update(_DEFAULT_FLAGS)