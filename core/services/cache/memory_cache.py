"""
In-memory LRU cache implementation.

Thread-safe cache with configurable size limits and TTL.
"""
from collections import OrderedDict
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Optional, List

from .cache_interface import ICache, CacheEntry, CacheStats


class MemoryCache(ICache[Any]):
    """Thread-safe in-memory LRU cache."""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[timedelta] = None
    ):
        """Initialize memory cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live (None = no expiration)
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl or timedelta(hours=1)
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1

            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> None:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live (uses default if not provided)
        """
        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                # Remove oldest (first) item
                self._cache.popitem(last=False)
                self._evictions += 1

            # Calculate expiration
            actual_ttl = ttl or self._default_ttl
            expires_at = datetime.now() + actual_ttl if actual_ttl else None

            # Store entry
            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at
            )

            # Move to end (most recently used)
            self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """Remove entry from cache.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def contains(self, key: str) -> bool:
        """Check if key exists and is valid.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache[key]
            if entry.is_expired:
                del self._cache[key]
                return False

            return True

    @property
    def stats(self) -> CacheStats:
        """Return cache statistics.

        Returns:
            CacheStats instance
        """
        with self._lock:
            return CacheStats(
                size=len(self._cache),
                max_size=self._max_size,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions
            )

    def keys(self) -> List[str]:
        """Get all valid cache keys.

        Returns:
            List of keys (non-expired only)
        """
        with self._lock:
            valid_keys = []
            expired_keys = []

            for key, entry in self._cache.items():
                if entry.is_expired:
                    expired_keys.append(key)
                else:
                    valid_keys.append(key)

            # Clean up expired entries
            for key in expired_keys:
                del self._cache[key]

            return valid_keys

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]

            for key in expired:
                del self._cache[key]

            return len(expired)

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry with metadata.

        Args:
            key: Cache key

        Returns:
            CacheEntry or None
        """
        with self._lock:
            return self._cache.get(key)
