"""
Interfaces for dependency inversion following SOLID principles.

This module exports all interface contracts used throughout the application.
External dependencies should depend on these abstractions, not concrete implementations.
"""
from .config_provider import (
    IADOConfig,
    IApplicationConfig,
    IConfigProvider,
    IRulesConfig,
)
from .llm_provider import ILLMProvider
from .metrics import (
    CacheMetrics,
    GenerationMetrics,
    IMetricsCollector,
    MetricType,
    ParsingMetrics,
    TokenUsage,
)
from .output_generator import ICSVGenerator, IObjectiveGenerator, IOutputGenerator
from .quality_standards import (
    GENERIC_PHRASES,
    QUALITY_THRESHOLDS,
    CorrectionResult,
    IQualityAnalyzer,
    ITestCorrector,
    QualityIssue,
    QualityLevel,
    StepQualityMetrics,
    TestCaseQualityMetrics,
)
from .repository import IStoryRepository, ITestCaseRepository, ITestSuiteRepository
from .semantic_parser import ISemanticParser, SemanticComponents
from .step_builder import IStepBuilder, IStepTemplate
from .test_generator import ITestGenerator
from .validator import IQualityGate, IValidator

__all__ = [
    # Repository interfaces
    'IStoryRepository',
    'ITestSuiteRepository',
    'ITestCaseRepository',
    # Generator interfaces
    'ITestGenerator',
    'IStepBuilder',
    'IStepTemplate',
    # Config interfaces
    'IConfigProvider',
    'IApplicationConfig',
    'IADOConfig',
    'IRulesConfig',
    # Output interfaces
    'IOutputGenerator',
    'ICSVGenerator',
    'IObjectiveGenerator',
    # Validation interfaces
    'IValidator',
    'IQualityGate',
    # LLM interfaces
    'ILLMProvider',
    # Metrics interfaces
    'IMetricsCollector',
    'GenerationMetrics',
    'TokenUsage',
    'ParsingMetrics',
    'CacheMetrics',
    'MetricType',
    # Semantic parser interfaces
    'ISemanticParser',
    'SemanticComponents',
    # Quality standards interfaces
    'IQualityAnalyzer',
    'ITestCorrector',
    'QualityLevel',
    'TestCaseQualityMetrics',
    'StepQualityMetrics',
    'QualityIssue',
    'CorrectionResult',
    'QUALITY_THRESHOLDS',
    'GENERIC_PHRASES',
]
