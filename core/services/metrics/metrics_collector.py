"""
Metrics collector implementation.

Collects, aggregates, and exports metrics for LLM usage and performance.
"""
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from core.interfaces.metrics import (
    IMetricsCollector,
    GenerationMetrics,
    TokenUsage,
    CacheMetrics
)
from .cost_calculator import CostCalculator
from .logger import StructuredLogger


class MetricsCollector(IMetricsCollector):
    """Collects and aggregates metrics for monitoring and analysis."""

    def __init__(
        self,
        log_level: int = logging.INFO,
        enable_logging: bool = True
    ):
        """Initialize metrics collector.

        Args:
            log_level: Logging level for structured logger
            enable_logging: Enable structured logging
        """
        self._generations: List[GenerationMetrics] = []
        self._cache_metrics: Dict[str, CacheMetrics] = {}
        self._parsing_times: List[Dict] = []

        # Track cache hits/misses by provider
        self._cache_hits = defaultdict(int)
        self._cache_misses = defaultdict(int)

        # Structured logger
        self._enable_logging = enable_logging
        if enable_logging:
            self._logger = StructuredLogger(
                name="test_gen.metrics",
                level=log_level
            )
        else:
            self._logger = None

    def record_generation(self, metrics: GenerationMetrics) -> None:
        """Record an LLM generation request.

        Args:
            metrics: Generation metrics to record
        """
        self._generations.append(metrics)

        if self._logger:
            self._logger.log_generation(
                request_id=metrics.request_id,
                provider=metrics.provider,
                model=metrics.model,
                duration_ms=metrics.duration_ms,
                input_tokens=metrics.token_usage.input_tokens,
                output_tokens=metrics.token_usage.output_tokens,
                cost_usd=metrics.estimated_cost_usd,
                cache_hit=metrics.cache_hit,
                success=metrics.success,
                error=metrics.error_message
            )

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
        self._parsing_times.append({
            "parser": parser,
            "duration_ms": duration_ms,
            "success": success,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        if self._logger:
            self._logger.log_parsing(
                parser=parser,
                duration_ms=duration_ms,
                success=success,
                confidence=confidence
            )

    def record_cache_hit(
        self,
        cache_type: str,
        provider: str,
        model: str
    ) -> None:
        """Record a cache hit.

        Args:
            cache_type: Type of cache (memory/file)
            provider: LLM provider name
            model: Model name
        """
        key = f"{cache_type}:{provider}:{model}"
        self._cache_hits[key] += 1

        if key not in self._cache_metrics:
            self._cache_metrics[key] = CacheMetrics(cache_type=cache_type)
        self._cache_metrics[key].hits += 1

    def record_cache_miss(
        self,
        cache_type: str,
        provider: str,
        model: str
    ) -> None:
        """Record a cache miss.

        Args:
            cache_type: Type of cache (memory/file)
            provider: LLM provider name
            model: Model name
        """
        key = f"{cache_type}:{provider}:{model}"
        self._cache_misses[key] += 1

        if key not in self._cache_metrics:
            self._cache_metrics[key] = CacheMetrics(cache_type=cache_type)
        self._cache_metrics[key].misses += 1

    def get_summary(self) -> Dict:
        """Get aggregated metrics summary.

        Returns:
            Dictionary with metrics summary
        """
        if not self._generations:
            return {
                "message": "No metrics collected",
                "total_requests": 0,
                "total_cost_usd": 0.0
            }

        total_tokens = sum(
            g.token_usage.total_tokens for g in self._generations
        )
        total_cost = sum(g.estimated_cost_usd for g in self._generations)
        total_duration = sum(g.duration_ms for g in self._generations)
        successful = sum(1 for g in self._generations if g.success)
        cache_hits = sum(1 for g in self._generations if g.cache_hit)

        return {
            "total_requests": len(self._generations),
            "successful_requests": successful,
            "failed_requests": len(self._generations) - successful,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hits / len(self._generations) if self._generations else 0.0,
            "total_tokens": total_tokens,
            "total_input_tokens": sum(
                g.token_usage.input_tokens for g in self._generations
            ),
            "total_output_tokens": sum(
                g.token_usage.output_tokens for g in self._generations
            ),
            "total_cost_usd": round(total_cost, 6),
            "total_duration_ms": round(total_duration, 2),
            "avg_duration_ms": round(
                total_duration / len(self._generations), 2
            ),
            "avg_tokens_per_request": round(
                total_tokens / len(self._generations), 1
            ),
            "by_provider": self._group_by_provider(),
            "by_model": self._group_by_model()
        }

    def get_cost_report(self) -> Dict:
        """Get detailed cost breakdown.

        Returns:
            Dictionary with cost breakdown by model/provider
        """
        by_model: Dict[str, Dict] = defaultdict(
            lambda: {"requests": 0, "tokens": 0, "cost": 0.0}
        )
        by_provider: Dict[str, Dict] = defaultdict(
            lambda: {"requests": 0, "tokens": 0, "cost": 0.0}
        )

        for gen in self._generations:
            # By model
            model = gen.model
            by_model[model]["requests"] += 1
            by_model[model]["tokens"] += gen.token_usage.total_tokens
            by_model[model]["cost"] += gen.estimated_cost_usd

            # By provider
            provider = gen.provider
            by_provider[provider]["requests"] += 1
            by_provider[provider]["tokens"] += gen.token_usage.total_tokens
            by_provider[provider]["cost"] += gen.estimated_cost_usd

        # Round costs
        for model_data in by_model.values():
            model_data["cost"] = round(model_data["cost"], 6)
        for provider_data in by_provider.values():
            provider_data["cost"] = round(provider_data["cost"], 6)

        total_cost = sum(g.estimated_cost_usd for g in self._generations)

        result = {
            "total_cost_usd": round(total_cost, 6),
            "formatted_cost": CostCalculator.format_cost(total_cost),
            "by_model": dict(by_model),
            "by_provider": dict(by_provider)
        }

        if self._generations:
            result["period"] = {
                "start": min(g.start_time for g in self._generations).isoformat(),
                "end": max(g.end_time for g in self._generations).isoformat()
            }

        return result

    def export(self, format: str = "json") -> str:
        """Export metrics in specified format.

        Args:
            format: Export format ('json' or 'csv')

        Returns:
            Formatted metrics string
        """
        if format == "json":
            return self._export_json()
        elif format == "csv":
            return self._export_csv()
        else:
            raise ValueError(f"Unsupported format: {format}")

    def reset(self) -> None:
        """Reset all collected metrics."""
        self._generations.clear()
        self._cache_metrics.clear()
        self._parsing_times.clear()
        self._cache_hits.clear()
        self._cache_misses.clear()

    def _group_by_provider(self) -> Dict[str, Dict]:
        """Group metrics by provider."""
        result: Dict[str, Dict] = defaultdict(
            lambda: {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
                "avg_duration_ms": 0.0
            }
        )

        for gen in self._generations:
            provider = gen.provider
            result[provider]["requests"] += 1
            result[provider]["tokens"] += gen.token_usage.total_tokens
            result[provider]["cost"] += gen.estimated_cost_usd
            result[provider]["avg_duration_ms"] += gen.duration_ms

        # Calculate averages
        for provider, data in result.items():
            if data["requests"] > 0:
                data["avg_duration_ms"] = round(
                    data["avg_duration_ms"] / data["requests"], 2
                )
            data["cost"] = round(data["cost"], 6)

        return dict(result)

    def _group_by_model(self) -> Dict[str, Dict]:
        """Group metrics by model."""
        result: Dict[str, Dict] = defaultdict(
            lambda: {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
                "avg_duration_ms": 0.0
            }
        )

        for gen in self._generations:
            model = gen.model
            result[model]["requests"] += 1
            result[model]["tokens"] += gen.token_usage.total_tokens
            result[model]["cost"] += gen.estimated_cost_usd
            result[model]["avg_duration_ms"] += gen.duration_ms

        # Calculate averages
        for model, data in result.items():
            if data["requests"] > 0:
                data["avg_duration_ms"] = round(
                    data["avg_duration_ms"] / data["requests"], 2
                )
            data["cost"] = round(data["cost"], 6)

        return dict(result)

    def _export_json(self) -> str:
        """Export metrics as JSON."""
        data = {
            "summary": self.get_summary(),
            "cost_report": self.get_cost_report(),
            "cache_metrics": {
                k: {
                    "cache_type": v.cache_type,
                    "hits": v.hits,
                    "misses": v.misses,
                    "hit_rate": v.hit_rate
                }
                for k, v in self._cache_metrics.items()
            },
            "parsing_metrics": {
                "total_operations": len(self._parsing_times),
                "by_parser": self._aggregate_parsing_metrics()
            },
            "generations": [
                {
                    "request_id": g.request_id,
                    "provider": g.provider,
                    "model": g.model,
                    "duration_ms": g.duration_ms,
                    "tokens": g.token_usage.total_tokens,
                    "cost_usd": g.estimated_cost_usd,
                    "cache_hit": g.cache_hit,
                    "success": g.success,
                    "timestamp": g.start_time.isoformat()
                }
                for g in self._generations
            ]
        }
        return json.dumps(data, indent=2)

    def _export_csv(self) -> str:
        """Export generations as CSV."""
        lines = [
            "request_id,provider,model,duration_ms,input_tokens,output_tokens,cost_usd,cache_hit,success,timestamp"
        ]

        for g in self._generations:
            lines.append(
                f"{g.request_id},{g.provider},{g.model},{g.duration_ms},"
                f"{g.token_usage.input_tokens},{g.token_usage.output_tokens},"
                f"{g.estimated_cost_usd},{g.cache_hit},{g.success},"
                f"{g.start_time.isoformat()}"
            )

        return "\n".join(lines)

    def _aggregate_parsing_metrics(self) -> Dict[str, Dict]:
        """Aggregate parsing metrics by parser type."""
        result: Dict[str, Dict] = defaultdict(
            lambda: {
                "count": 0,
                "avg_duration_ms": 0.0,
                "success_rate": 0.0,
                "avg_confidence": 0.0
            }
        )

        for p in self._parsing_times:
            parser = p["parser"]
            result[parser]["count"] += 1
            result[parser]["avg_duration_ms"] += p["duration_ms"]
            result[parser]["success_rate"] += 1 if p["success"] else 0
            result[parser]["avg_confidence"] += p["confidence"]

        for parser, data in result.items():
            if data["count"] > 0:
                data["avg_duration_ms"] = round(
                    data["avg_duration_ms"] / data["count"], 2
                )
                data["success_rate"] = round(
                    data["success_rate"] / data["count"], 3
                )
                data["avg_confidence"] = round(
                    data["avg_confidence"] / data["count"], 3
                )

        return dict(result)


# Global metrics collector instance
_global_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector.

    Returns:
        Global MetricsCollector instance
    """
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def reset_metrics() -> None:
    """Reset global metrics collector."""
    global _global_collector
    if _global_collector:
        _global_collector.reset()
