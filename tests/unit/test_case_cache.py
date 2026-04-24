"""Unit tests for case cache helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.cache import CaseCache
from src.case import CaseFile, CaseMeta, Step


def test_case_cache_uses_md5_key() -> None:
    cache = CaseCache()

    key = cache.get_cache_key("登录 GitHub", "Safari")

    assert key == hashlib.md5("登录 GitHub:Safari".encode("utf-8")).hexdigest()


def test_case_cache_round_trips_case(tmp_path: Path) -> None:
    cache = CaseCache(cache_dir=tmp_path / ".gda" / "cache")
    case = CaseFile(
        meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
        steps=[Step(action="tap", target="Sign in")],
    )

    cache_path = cache.put("登录 GitHub", "Safari", case)
    loaded = cache.get("登录 GitHub", "Safari")

    assert cache_path.exists()
    assert loaded == case


def test_case_cache_returns_none_for_miss(tmp_path: Path) -> None:
    cache = CaseCache(cache_dir=tmp_path / ".gda" / "cache")

    loaded = cache.get("搜索天气", "Safari")

    assert loaded is None
