"""
Interfaces for dependency inversion following SOLID principles.

This module exports all interface contracts used throughout the application.
External dependencies should depend on these abstractions, not concrete implementations.
"""
from .repository import IStoryRepository, ITestSuiteRepository, ITestCaseRepository
from .test_generator import ITestGenerator
from .config_provider import IConfigProvider, IApplicationConfig, IADOConfig, IRulesConfig
from .step_builder import IStepBuilder, IStepTemplate
from .output_generator import IOutputGenerator, ICSVGenerator, IObjectiveGenerator
from .validator import IValidator, IQualityGate
from .llm_provider import ILLMProvider
from .metrics import (
    IMetricsCollector,
    GenerationMetrics,
    TokenUsage,
    ParsingMetrics,
    CacheMetrics,
    MetricType
)
from .semantic_parser import ISemanticParser, SemanticComponents
from .quality_standards import (
    IQualityAnalyzer,
    ITestCorrector,
    QualityLevel,
    TestCaseQualityMetrics,
    StepQualityMetrics,
    QualityIssue,
    CorrectionResult,
    QUALITY_THRESHOLDS,
    GENERIC_PHRASES,
)

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
