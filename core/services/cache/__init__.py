"""
Caching services for LLM responses and parsed semantics.

Provides multi-level caching with memory and file-based backends.
"""
from .cache_interface import CacheEntry, CacheStats, ICache
from .cache_manager import CacheManager, clear_global_cache, get_cache_manager
from .file_cache import FileCache
from .memory_cache import MemoryCache

__all__ = [
    'CacheEntry',
    'CacheManager',
    'CacheStats',
    'FileCache',
    'ICache',
    'MemoryCache',
    'clear_global_cache',
    'get_cache_manager'
]
