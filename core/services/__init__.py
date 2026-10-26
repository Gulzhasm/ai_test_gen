"""
Core services - business logic and domain services.
"""
from .ac_parser import ACParser, ACSemantics, ComprehensiveStepBuilder
from .cache import (
    CacheEntry,
    CacheManager,
    CacheStats,
    FileCache,
    ICache,
    MemoryCache,
    clear_global_cache,
    get_cache_manager,
)
from .linting import (
    ObjectiveLinter,
    SummaryLinter,
)
from .llm import (
    AnthropicProvider,
    CachedLLMProvider,
    LLMCorrector,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    PromptBuilder,
    build_prompts_for_project,
    create_llm_provider,
    wrap_with_cache,
)
from .metrics import (
    CostCalculator,
    MetricsCollector,
    ModelPricing,
    StructuredLogger,
    get_metrics_collector,
    reset_metrics,
)
from .nlp import SPACY_AVAILABLE, HybridACParser, SpacySemanticParser
from .objective_service import ObjectiveService
from .quality import (
    BatchTestCorrector,
    LLMTestCorrector,
    SemanticStepBuilder,
    TestQualityAnalyzer,
    get_quality_analyzer,
    get_semantic_step_builder,
)
from .summary_service import SummaryService
from .test_generator import GenericTestGenerator
from .test_rules import StepTemplate, TestRules
from .test_validator import TestCaseValidator, ValidationResult, ValidationSeverity

__all__ = [
    'ACParser',
    'ACSemantics',
    'ComprehensiveStepBuilder',
    'TestRules',
    'StepTemplate',
    'TestCaseValidator',
    'ValidationResult',
    'ValidationSeverity',
    'GenericTestGenerator',
    'ObjectiveService',
    'SummaryService',
    # Metrics
    'CostCalculator',
    'ModelPricing',
    'StructuredLogger',
    'MetricsCollector',
    'get_metrics_collector',
    'reset_metrics',
    # Cache
    'ICache',
    'CacheEntry',
    'CacheStats',
    'MemoryCache',
    'FileCache',
    'CacheManager',
    'get_cache_manager',
    'clear_global_cache',
    # NLP
    'SpacySemanticParser',
    'HybridACParser',
    'SPACY_AVAILABLE',
    # Quality
    'TestQualityAnalyzer',
    'get_quality_analyzer',
    'LLMTestCorrector',
    'BatchTestCorrector',
    'SemanticStepBuilder',
    'get_semantic_step_builder',
    # Linting
    'SummaryLinter',
    'ObjectiveLinter',
    # LLM
    'LLMProvider',
    'OllamaProvider',
    'OpenAIProvider',
    'AnthropicProvider',
    'CachedLLMProvider',
    'wrap_with_cache',
    'create_llm_provider',
    'LLMCorrector',
    'PromptBuilder',
    'build_prompts_for_project',
]
