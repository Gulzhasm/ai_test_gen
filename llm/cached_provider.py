"""
Cached LLM Provider Wrapper.

Wraps any LLM provider to add caching capabilities.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.interfaces.llm_provider import ILLMProvider, LLMResponse
from core.interfaces.metrics import GenerationMetrics, TokenUsage
from core.services.cache.cache_manager import CacheManager
from core.services.metrics.cost_calculator import CostCalculator


class CachedLLMProvider(ILLMProvider):
    """Wrapper that adds caching to any LLM provider."""

    def __init__(
        self,
        provider: ILLMProvider,
        cache_manager: Optional[CacheManager] = None,
        cache_ttl: Optional[timedelta] = None,
        metrics_collector: Optional[Any] = None
    ):
        """Initialize cached provider.

        Args:
            provider: Underlying LLM provider
            cache_manager: Cache manager instance
            cache_ttl: Time-to-live for cached responses
            metrics_collector: Optional metrics collector
        """
        self._provider = provider
        self._cache = cache_manager or CacheManager()
        self._cache_ttl = cache_ttl or timedelta(hours=24)
        self._metrics = metrics_collector

    @property
    def provider_name(self) -> str:
        """Name of the underlying provider."""
        return self._provider.provider_name

    @property
    def model(self) -> str:
        """Model being used."""
        return self._provider.model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text with caching.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            LLMResponse (from cache or fresh)
        """
        # Generate cache key
        cache_key = self._get_cache_key(prompt, system_prompt, "generate")

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            # Record cache hit
            if self._metrics:
                self._metrics.record_cache_hit(
                    cache_type="llm",
                    provider=self.provider_name,
                    model=self.model
                )

            # Return cached response
            return self._deserialize_response(cached)

        # Record cache miss
        if self._metrics:
            self._metrics.record_cache_miss(
                cache_type="llm",
                provider=self.provider_name,
                model=self.model
            )

        # Generate fresh response
        start_time = datetime.now()
        response = self._provider.generate(prompt, system_prompt, **kwargs)
        end_time = datetime.now()

        # Record metrics
        if self._metrics and response.usage:
            cost = CostCalculator.calculate_cost(
                model=self.model,
                input_tokens=response.usage.get("input_tokens", 0),
                output_tokens=response.usage.get("output_tokens", 0)
            )

            metrics = GenerationMetrics(
                request_id=str(uuid.uuid4())[:8],
                provider=self.provider_name,
                model=self.model,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                token_usage=TokenUsage(
                    input_tokens=response.usage.get("input_tokens", 0),
                    output_tokens=response.usage.get("output_tokens", 0),
                    total_tokens=response.usage.get("total_tokens", 0),
                    model=self.model
                ),
                estimated_cost_usd=cost,
                cache_hit=False
            )
            self._metrics.record_generation(metrics)

        # Cache the response
        self._cache.set(
            cache_key,
            self._serialize_response(response),
            self._cache_ttl
        )

        return response

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON with caching.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary
        """
        # Generate cache key
        cache_key = self._get_cache_key(prompt, system_prompt, "json")

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            if self._metrics:
                self._metrics.record_cache_hit(
                    cache_type="llm_json",
                    provider=self.provider_name,
                    model=self.model
                )
            return cached  # JSON is already dict

        if self._metrics:
            self._metrics.record_cache_miss(
                cache_type="llm_json",
                provider=self.provider_name,
                model=self.model
            )

        # Generate fresh response
        result = self._provider.generate_json(prompt, system_prompt, **kwargs)

        # Cache the result
        self._cache.set(cache_key, result, self._cache_ttl)

        return result

    def is_available(self) -> bool:
        """Check if underlying provider is available."""
        return self._provider.is_available()

    def _get_cache_key(
        self,
        prompt: str,
        system_prompt: Optional[str],
        method: str
    ) -> str:
        """Generate cache key for request.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            method: Method name (generate/json)

        Returns:
            Cache key string
        """
        return f"llm:{method}:{CacheManager.hash_prompt(prompt, system_prompt, self.model)}"

    def _serialize_response(self, response: LLMResponse) -> Dict[str, Any]:
        """Serialize LLMResponse for caching.

        Args:
            response: Response to serialize

        Returns:
            Dictionary representation
        """
        return {
            "content": response.content,
            "model": response.model,
            "usage": response.usage,
            "finish_reason": response.finish_reason
        }

    def _deserialize_response(self, data: Dict[str, Any]) -> LLMResponse:
        """Deserialize cached response.

        Args:
            data: Cached dictionary

        Returns:
            LLMResponse instance
        """
        return LLMResponse(
            content=data["content"],
            model=data["model"],
            usage=data.get("usage"),
            finish_reason=data.get("finish_reason")
        )

    def clear_cache(self) -> None:
        """Clear the LLM response cache."""
        self._cache.clear()

    @property
    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics dictionary
        """
        return self._cache.stats


def wrap_with_cache(
    provider: ILLMProvider,
    cache_manager: Optional[CacheManager] = None,
    cache_ttl: Optional[timedelta] = None,
    metrics_collector: Optional[Any] = None
) -> CachedLLMProvider:
    """Convenience function to wrap a provider with caching.

    Args:
        provider: LLM provider to wrap
        cache_manager: Optional cache manager
        cache_ttl: Cache TTL
        metrics_collector: Optional metrics collector

    Returns:
        Cached provider wrapper
    """
    return CachedLLMProvider(
        provider=provider,
        cache_manager=cache_manager,
        cache_ttl=cache_ttl,
        metrics_collector=metrics_collector
    )
