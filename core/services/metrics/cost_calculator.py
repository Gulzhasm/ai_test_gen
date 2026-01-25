"""
Cost calculator for LLM usage.

Calculates estimated costs based on token usage and model pricing.
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ModelPricing:
    """Pricing per 1 million tokens."""
    input_cost: float   # USD per 1M input tokens
    output_cost: float  # USD per 1M output tokens

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for given token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * self.input_cost
        output_cost = (output_tokens / 1_000_000) * self.output_cost
        return input_cost + output_cost


class CostCalculator:
    """Calculate costs for LLM usage across different providers."""

    # Pricing as of January 2025 (per 1M tokens)
    PRICING: Dict[str, ModelPricing] = {
        # OpenAI models
        "gpt-4o-mini": ModelPricing(0.15, 0.60),
        "gpt-4o": ModelPricing(2.50, 10.00),
        "gpt-4-turbo": ModelPricing(10.00, 30.00),
        "gpt-4": ModelPricing(30.00, 60.00),
        "gpt-3.5-turbo": ModelPricing(0.50, 1.50),

        # Anthropic models
        "claude-3-5-sonnet-20241022": ModelPricing(3.00, 15.00),
        "claude-3-5-sonnet": ModelPricing(3.00, 15.00),
        "claude-3-haiku-20240307": ModelPricing(0.25, 1.25),
        "claude-3-haiku": ModelPricing(0.25, 1.25),
        "claude-3-opus-20240229": ModelPricing(15.00, 75.00),
        "claude-3-opus": ModelPricing(15.00, 75.00),
        "claude-3-sonnet": ModelPricing(3.00, 15.00),

        # Ollama models (local, no cost)
        "llama3.2:3b": ModelPricing(0.0, 0.0),
        "llama3.2:1b": ModelPricing(0.0, 0.0),
        "llama3.1:8b": ModelPricing(0.0, 0.0),
        "llama3.1:70b": ModelPricing(0.0, 0.0),
        "mistral": ModelPricing(0.0, 0.0),
        "codellama": ModelPricing(0.0, 0.0),
        "phi3": ModelPricing(0.0, 0.0),
    }

    @classmethod
    def get_pricing(cls, model: str) -> Optional[ModelPricing]:
        """Get pricing for a model.

        Args:
            model: Model name or identifier

        Returns:
            ModelPricing or None if unknown
        """
        # Try exact match first
        if model in cls.PRICING:
            return cls.PRICING[model]

        # Try partial match (model might include version)
        model_lower = model.lower()
        for known_model, pricing in cls.PRICING.items():
            if known_model in model_lower or model_lower in known_model:
                return pricing

        return None

    @classmethod
    def calculate_cost(
        cls,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost in USD.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD (0.0 if model unknown or local)
        """
        pricing = cls.get_pricing(model)
        if pricing is None:
            return 0.0

        return pricing.calculate_cost(input_tokens, output_tokens)

    @classmethod
    def is_local_model(cls, model: str) -> bool:
        """Check if model is a local/free model.

        Args:
            model: Model name

        Returns:
            True if model is local (no API cost)
        """
        pricing = cls.get_pricing(model)
        if pricing is None:
            # Unknown models assumed to be local
            return True
        return pricing.input_cost == 0.0 and pricing.output_cost == 0.0

    @classmethod
    def format_cost(cls, cost_usd: float) -> str:
        """Format cost for display.

        Args:
            cost_usd: Cost in USD

        Returns:
            Formatted string
        """
        if cost_usd == 0.0:
            return "Free (local)"
        elif cost_usd < 0.01:
            return f"${cost_usd:.6f}"
        elif cost_usd < 1.00:
            return f"${cost_usd:.4f}"
        else:
            return f"${cost_usd:.2f}"

    @classmethod
    def estimate_batch_cost(
        cls,
        model: str,
        num_requests: int,
        avg_input_tokens: int = 500,
        avg_output_tokens: int = 1000
    ) -> float:
        """Estimate cost for a batch of requests.

        Args:
            model: Model name
            num_requests: Number of requests
            avg_input_tokens: Average input tokens per request
            avg_output_tokens: Average output tokens per request

        Returns:
            Estimated total cost in USD
        """
        single_cost = cls.calculate_cost(
            model,
            avg_input_tokens,
            avg_output_tokens
        )
        return single_cost * num_requests
