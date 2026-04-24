"""Filesystem-backed cache for recorded case files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.case import CaseFile, load_case, save_case


class CaseCache:
    """Persist and retrieve recorded cases by goal and app."""

    def __init__(self, cache_dir: str | Path = ".gda/cache") -> None:
        self.cache_dir = Path(cache_dir)

    def get_cache_key(self, goal: str, app: str) -> str:
        """Build a stable cache key for one goal/app pair."""
        return hashlib.md5(f"{goal}:{app}".encode("utf-8")).hexdigest()

    def get(self, goal: str, app: str) -> CaseFile | None:
        """Load a cached case when present."""
        cache_path = self._cache_path(goal, app)
        if not cache_path.exists():
            return None
        return load_case(cache_path)

    def put(self, goal: str, app: str, case: CaseFile) -> Path:
        """Store one case in the cache and return its path."""
        cache_path = self._cache_path(goal, app)
        save_case(case, cache_path)
        return cache_path

    def _cache_path(self, goal: str, app: str) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"{self.get_cache_key(goal, app)}.yaml"
