"""Shared key-rotation pool for free-tier LLM/API providers (AI cascade
restructure, scratch/restructure-plan.md).

Provider-agnostic: round-robins up to ``max_keys`` keys loaded from
``{env_prefix}_1`` .. ``{env_prefix}_{max_keys}``, skipping unset slots, so
it works with fewer than ``max_keys`` configured (local dev, or a provider
not yet fully signed up for). In-process state only (a dict of
``key -> cooldown_until``) -- no new persistence layer, matching this
being a single-instance deployment. Never raises: a caller that finds no
usable key should fall through to the next cascade tier.
"""
import os
import time


class KeyPool:
    def __init__(self, provider_name: str, env_prefix: str, max_keys: int = 9, cooldown_s: float = 60.0):
        self.provider_name = provider_name
        self.cooldown_s = cooldown_s
        self._keys = [
            key
            for i in range(1, max_keys + 1)
            if (key := os.environ.get(f"{env_prefix}_{i}", "").strip())
        ]
        self._cooldown_until: dict[str, float] = {}
        self._next_index = 0

    def get_key(self) -> str | None:
        """Next usable key, round-robin, skipping any still cooling down."""
        if not self._keys:
            return None
        now = time.monotonic()
        for _ in range(len(self._keys)):
            key = self._keys[self._next_index % len(self._keys)]
            self._next_index += 1
            if self._cooldown_until.get(key, 0.0) <= now:
                return key
        return None  # every key is currently cooling down

    def mark_rate_limited(self, key: str) -> None:
        self._cooldown_until[key] = time.monotonic() + self.cooldown_s

    def mark_success(self, key: str) -> None:
        self._cooldown_until.pop(key, None)

    def all_exhausted(self) -> bool:
        if not self._keys:
            return True
        now = time.monotonic()
        return all(self._cooldown_until.get(key, 0.0) > now for key in self._keys)

    def key_count(self) -> int:
        return len(self._keys)
