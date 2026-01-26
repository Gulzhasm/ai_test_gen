"""
Core services - business logic and domain services.
"""
from .ac_parser import ACParser, ACSemantics, ComprehensiveStepBuilder
from .test_rules import TestRules, StepTemplate
from .test_validator import TestCaseValidator, ValidationResult, ValidationSeverity
from .test_generator import GenericTestGenerator
from .objective_service import ObjectiveService
from .summary_service import SummaryService
from .metrics import (
    CostCalculator,
    ModelPricing,
    StructuredLogger,
    MetricsCollector,
    get_metrics_collector,
    reset_metrics
)
from .cache import (
    ICache,
    CacheEntry,
    CacheStats,
    MemoryCache,
    FileCache,
    CacheManager,
    get_cache_manager,
    clear_global_cache
)
from .nlp import (
    SpacySemanticParser,
    HybridACParser,
    SPACY_AVAILABLE
)
from .quality import (
    TestQualityAnalyzer,
    get_quality_analyzer,
    LLMTestCorrector,
    BatchTestCorrector,
    SemanticStepBuilder,
    get_semantic_step_builder,
)
from .linting import (
    SummaryLinter,
    ObjectiveLinter,
)
from .llm import (
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    AnthropicProvider,
    CachedLLMProvider,
    wrap_with_cache,
    create_llm_provider,
    LLMCorrector,
    PromptBuilder,
    build_prompts_for_project,
)

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
