"""
Cache interface definitions.

Provides abstract base class for cache implementations.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Generic, Optional, TypeVar

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""
    key: str
    value: T
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired.

        Returns:
            True if entry is expired
        """
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds.

        Returns:
            Age in seconds
        """
        return (datetime.now() - self.created_at).total_seconds()

    def touch(self) -> None:
        """Update access count."""
        self.hit_count += 1


@dataclass
class CacheStats:
    """Statistics for a cache."""
    size: int
    max_size: int
    hits: int
    misses: int
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate.

        Returns:
            Hit rate as float (0-1)
        """
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def usage_percent(self) -> float:
        """Calculate usage percentage.

        Returns:
            Usage as percentage (0-100)
        """
        return (self.size / self.max_size * 100) if self.max_size > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "size": self.size,
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4),
            "usage_percent": round(self.usage_percent, 2)
        }


class ICache(ABC, Generic[T]):
    """Interface for cache implementations."""

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        value: T,
        ttl: Optional[timedelta] = None
    ) -> None:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live (optional, uses default if not provided)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove entry from cache.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    def contains(self, key: str) -> bool:
        """Check if key exists and is valid.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        pass

    @property
    @abstractmethod
    def stats(self) -> CacheStats:
        """Return cache statistics.

        Returns:
            CacheStats instance
        """
        pass

    @abstractmethod
    def keys(self) -> list:
        """Get all valid cache keys.

        Returns:
            List of keys
        """
        pass
