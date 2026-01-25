"""
Caching services for LLM responses and parsed semantics.

Provides multi-level caching with memory and file-based backends.
"""
from .cache_interface import ICache, CacheEntry, CacheStats
from .memory_cache import MemoryCache
from .file_cache import FileCache
from .cache_manager import CacheManager, get_cache_manager, clear_global_cache

__all__ = [
    'ICache',
    'CacheEntry',
    'CacheStats',
    'MemoryCache',
    'FileCache',
    'CacheManager',
    'get_cache_manager',
    'clear_global_cache'
]
