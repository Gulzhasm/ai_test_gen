"""
Cache manager for multi-level caching.

Provides unified access to memory and file caches with automatic fallback.
"""
import hashlib
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

from .cache_interface import CacheStats
from .memory_cache import MemoryCache
from .file_cache import FileCache


class CacheManager:
    """Unified cache manager with multiple cache levels."""

    def __init__(
        self,
        enable_memory: bool = True,
        enable_file: bool = True,
        cache_dir: str = ".cache",
        memory_max_size: int = 500,
        file_max_size: int = 10000,
        memory_ttl: Optional[timedelta] = None,
        file_ttl: Optional[timedelta] = None
    ):
        """Initialize cache manager.

        Args:
            enable_memory: Enable in-memory cache
            enable_file: Enable file-based cache
            cache_dir: Directory for file cache
            memory_max_size: Max entries in memory cache
            file_max_size: Max entries in file cache
            memory_ttl: Memory cache TTL (default 1 hour)
            file_ttl: File cache TTL (default 7 days)
        """
        self._memory_cache: Optional[MemoryCache] = None
        self._file_cache: Optional[FileCache] = None
        self._enable_memory = enable_memory
        self._enable_file = enable_file

        if enable_memory:
            self._memory_cache = MemoryCache(
                max_size=memory_max_size,
                default_ttl=memory_ttl or timedelta(hours=1)
            )

        if enable_file:
            self._file_cache = FileCache(
                cache_dir=cache_dir,
                max_size=file_max_size,
                default_ttl=file_ttl or timedelta(days=7)
            )

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (checks memory first, then file).

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        # Try memory cache first
        if self._memory_cache:
            value = self._memory_cache.get(key)
            if value is not None:
                return value

        # Try file cache
        if self._file_cache:
            value = self._file_cache.get(key)
            if value is not None:
                # Populate memory cache for faster subsequent access
                if self._memory_cache:
                    self._memory_cache.set(key, value)
                return value

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None,
        memory_only: bool = False
    ) -> None:
        """Store value in cache(s).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live
            memory_only: Only store in memory cache
        """
        if self._memory_cache:
            self._memory_cache.set(key, value, ttl)

        if self._file_cache and not memory_only:
            self._file_cache.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete from all caches.

        Args:
            key: Cache key

        Returns:
            True if deleted from any cache
        """
        deleted = False

        if self._memory_cache:
            deleted = self._memory_cache.delete(key) or deleted

        if self._file_cache:
            deleted = self._file_cache.delete(key) or deleted

        return deleted

    def clear(self) -> None:
        """Clear all caches."""
        if self._memory_cache:
            self._memory_cache.clear()

        if self._file_cache:
            self._file_cache.clear()

    def contains(self, key: str) -> bool:
        """Check if key exists in any cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        if self._memory_cache and self._memory_cache.contains(key):
            return True

        if self._file_cache and self._file_cache.contains(key):
            return True

        return False

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[timedelta] = None,
        memory_only: bool = False
    ) -> Any:
        """Get from cache or compute and store.

        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            ttl: Time-to-live
            memory_only: Only cache in memory

        Returns:
            Cached or computed value
        """
        # Try to get from cache
        value = self.get(key)
        if value is not None:
            return value

        # Compute value
        value = compute_fn()

        # Store in cache(s)
        self.set(key, value, ttl, memory_only)

        return value

    @staticmethod
    def hash_prompt(
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """Generate cache key from prompts.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            model: Model name (optional)

        Returns:
            SHA-256 hash as cache key
        """
        content = f"{system_prompt or ''}|{model or ''}|{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    @property
    def stats(self) -> Dict[str, Any]:
        """Get combined cache statistics.

        Returns:
            Dictionary with statistics for all caches
        """
        result = {
            "enabled": {
                "memory": self._enable_memory,
                "file": self._enable_file
            }
        }

        if self._memory_cache:
            result["memory"] = self._memory_cache.stats.to_dict()

        if self._file_cache:
            file_stats = self._file_cache.stats.to_dict()
            file_stats["disk_usage_bytes"] = self._file_cache.get_disk_usage()
            result["file"] = file_stats

        # Combined stats
        total_hits = 0
        total_misses = 0

        if self._memory_cache:
            total_hits += self._memory_cache.stats.hits
            total_misses += self._memory_cache.stats.misses

        if self._file_cache:
            total_hits += self._file_cache.stats.hits
            total_misses += self._file_cache.stats.misses

        total = total_hits + total_misses
        result["combined"] = {
            "total_hits": total_hits,
            "total_misses": total_misses,
            "hit_rate": round(total_hits / total, 4) if total > 0 else 0.0
        }

        return result

    def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired entries from all caches.

        Returns:
            Dictionary with cleanup counts per cache
        """
        result = {}

        if self._memory_cache:
            result["memory"] = self._memory_cache.cleanup_expired()

        if self._file_cache:
            result["file"] = self._file_cache.cleanup_expired()

        return result

    def keys(self) -> Dict[str, List[str]]:
        """Get all valid keys from all caches.

        Returns:
            Dictionary with keys per cache type
        """
        result = {}

        if self._memory_cache:
            result["memory"] = self._memory_cache.keys()

        if self._file_cache:
            result["file"] = self._file_cache.keys()

        return result


# Global cache manager instance
_global_cache: Optional[CacheManager] = None


def get_cache_manager(
    cache_dir: str = ".cache",
    enable_memory: bool = True,
    enable_file: bool = True
) -> CacheManager:
    """Get or create global cache manager.

    Args:
        cache_dir: Cache directory (only used on first call)
        enable_memory: Enable memory cache
        enable_file: Enable file cache

    Returns:
        Global CacheManager instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager(
            cache_dir=cache_dir,
            enable_memory=enable_memory,
            enable_file=enable_file
        )
    return _global_cache


def clear_global_cache() -> None:
    """Clear and reset global cache manager."""
    global _global_cache
    if _global_cache:
        _global_cache.clear()
    _global_cache = None
