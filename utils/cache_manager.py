"""
In-memory TTL cache manager using cachetools.
"""
import hashlib
import json

from cachetools import TTLCache

from utils.constants import CACHE_MAX_SIZE


class CacheManager:
    """Per-endpoint TTL caches keyed by endpoint + query params."""

    def __init__(self, max_size: int = CACHE_MAX_SIZE):
        self._max_size = max_size
        self._caches: dict[str, TTLCache] = {}

    def _get_cache(self, ttl: int) -> TTLCache:
        key = str(ttl)
        if key not in self._caches:
            self._caches[key] = TTLCache(maxsize=self._max_size, ttl=ttl)
        return self._caches[key]

    @staticmethod
    def make_cache_key(*args, **kwargs) -> str:
        """Deterministic cache key from args and kwargs."""
        raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, ttl: int, *args, **kwargs):
        """Get cached value or None."""
        cache = self._get_cache(ttl)
        key = self.make_cache_key(*args, **kwargs)
        return cache.get(key)

    def set(self, ttl: int, value, *args, **kwargs):
        """Store a value in the cache."""
        cache = self._get_cache(ttl)
        key = self.make_cache_key(*args, **kwargs)
        cache[key] = value

    def invalidate(self, ttl: int, *args, **kwargs):
        """Remove a specific entry."""
        cache = self._get_cache(ttl)
        key = self.make_cache_key(*args, **kwargs)
        cache.pop(key, None)

    def clear_all(self):
        """Clear all caches."""
        for cache in self._caches.values():
            cache.clear()


cache_manager = CacheManager()
