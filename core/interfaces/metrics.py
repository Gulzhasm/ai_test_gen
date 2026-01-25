"""
Metrics interface for tracking LLM usage, costs, and performance.

Provides structured metrics collection for monitoring and optimization.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMING = "timing"


@dataclass
class TokenUsage:
    """Token usage for a single LLM request."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GenerationMetrics:
    """Metrics for a single LLM generation request."""
    request_id: str
    provider: str
    model: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    token_usage: TokenUsage
    estimated_cost_usd: float
    cache_hit: bool = False
    success: bool = True
    error_message: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ms / 1000


@dataclass
class ParsingMetrics:
    """Metrics for AC parsing operations."""
    parser_type: str  # 'spacy', 'regex', 'hybrid'
    input_text: str
    duration_ms: float
    success: bool
    confidence: float = 1.0
    fallback_used: bool = False


@dataclass
class CacheMetrics:
    """Metrics for cache operations."""
    cache_type: str  # 'memory', 'file'
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class IMetricsCollector(ABC):
    """Interface for metrics collection implementations."""

    @abstractmethod
    def record_generation(self, metrics: GenerationMetrics) -> None:
        """Record an LLM generation request.

        Args:
            metrics: Generation metrics to record
        """
        pass

    @abstractmethod
    def record_parsing(
        self,
        parser: str,
        duration_ms: float,
        success: bool,
        confidence: float = 1.0
    ) -> None:
        """Record a parsing operation.

        Args:
            parser: Parser type used
            duration_ms: Duration in milliseconds
            success: Whether parsing succeeded
            confidence: Confidence score (0-1)
        """
        pass

    @abstractmethod
    def record_cache_hit(self, cache_type: str, provider: str, model: str) -> None:
        """Record a cache hit.

        Args:
            cache_type: Type of cache (memory/file)
            provider: LLM provider name
            model: Model name
        """
        pass

    @abstractmethod
    def record_cache_miss(self, cache_type: str, provider: str, model: str) -> None:
        """Record a cache miss.

        Args:
            cache_type: Type of cache (memory/file)
            provider: LLM provider name
            model: Model name
        """
        pass

    @abstractmethod
    def get_summary(self) -> Dict:
        """Get aggregated metrics summary.

        Returns:
            Dictionary with metrics summary
        """
        pass

    @abstractmethod
    def get_cost_report(self) -> Dict:
        """Get cost breakdown report.

        Returns:
            Dictionary with cost breakdown by model/provider
        """
        pass

    @abstractmethod
    def export(self, format: str = "json") -> str:
        """Export metrics in specified format.

        Args:
            format: Export format ('json', 'csv')

        Returns:
            Formatted metrics string
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset all collected metrics."""
        pass
