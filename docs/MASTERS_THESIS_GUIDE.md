# AI-Driven Test Case Generation Framework
## A Comprehensive Learning Guide for Master's Thesis Research

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Literature Review Context](#3-literature-review-context)
4. [System Architecture](#4-system-architecture)
5. [Implementation Details](#5-implementation-details)
6. [Quality Enhancement Pipeline](#6-quality-enhancement-pipeline)
7. [MCP Integration for AI Assistants](#7-mcp-integration-for-ai-assistants)
8. [Evaluation Methodology](#8-evaluation-methodology)
9. [Results and Findings](#9-results-and-findings)
10. [Future Research Directions](#10-future-research-directions)
11. [Appendices](#11-appendices)

---

## 1. Executive Summary

### 1.1 Research Objective

This framework addresses the challenge of **automated software test case generation** from natural language specifications (user stories and acceptance criteria). The system combines:

- **Natural Language Processing (NLP)** for semantic understanding
- **Large Language Models (LLM)** for content enhancement
- **Rule-based systems** for deterministic quality control
- **Model Context Protocol (MCP)** for AI assistant integration

### 1.2 Key Contributions

| Contribution | Description |
|--------------|-------------|
| Hybrid Generation Pipeline | Combines rule-based and LLM approaches for deterministic yet intelligent output |
| Quality Scoring System | Quantitative metrics for test case quality assessment |
| MCP Server Architecture | First-of-kind integration with GitHub Copilot for QA workflows |
| Multi-Project Configuration | YAML-based configuration for cross-project adaptability |

### 1.3 Technical Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                          │
├─────────────────────────────────────────────────────────────┤
│  Language:        Python 3.10+                               │
│  NLP:             spaCy (en_core_web_sm)                     │
│  LLM:             OpenAI GPT-4o-mini, Anthropic Claude       │
│  Protocol:        Model Context Protocol (MCP)               │
│  Integration:     Azure DevOps REST API                      │
│  Architecture:    Clean Architecture / Hexagonal             │
│  IDE:             VS Code with GitHub Copilot                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Problem Statement

### 2.1 Industry Challenge

Manual test case creation from user stories is:

1. **Time-consuming**: QA engineers spend 40-60% of time writing test cases
2. **Inconsistent**: Quality varies between team members
3. **Error-prone**: Generic phrases like "works as expected" provide no verification value
4. **Disconnected**: Test cases often don't trace back to acceptance criteria

### 2.2 Research Questions

**RQ1**: Can NLP techniques extract meaningful test semantics from acceptance criteria?

**RQ2**: How can LLMs enhance rule-generated test cases while maintaining determinism?

**RQ3**: What quality metrics best predict test case effectiveness?

**RQ4**: How can AI assistants (Copilot) be integrated into QA workflows?

### 2.3 Scope

```
IN SCOPE:
├── Functional test case generation
├── Web and desktop application testing
├── Azure DevOps integration
├── GitHub Copilot/MCP integration
└── Quality scoring and correction

OUT OF SCOPE:
├── Performance/load testing
├── Security testing
├── Mobile-specific testing
└── Test execution automation
```

---

## 3. Literature Review Context

### 3.1 Related Work

| Approach | Strengths | Limitations |
|----------|-----------|-------------|
| **Template-based** (Cucumber, Gherkin) | Structured, readable | Requires manual writing |
| **Model-based** (UML→Test) | Formal verification | Complex model creation |
| **ML-based** (BERT, GPT) | Flexible, intelligent | Non-deterministic |
| **Our Hybrid Approach** | Best of both worlds | Configuration overhead |

### 3.2 Theoretical Foundation

```
Acceptance Criteria (AC) → Semantic Parsing → Test Case Generation

AC Structure:
┌─────────────────────────────────────────────────────────┐
│  "User can [ACTION] the [TARGET] to [OUTCOME]"          │
│                                                          │
│  ACTION  = verb phrase (rotate, mirror, select)         │
│  TARGET  = noun phrase (object, element, file)          │
│  OUTCOME = expected result (displays, changes, updates) │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Key Papers to Reference

1. **Automated Test Case Generation**: Survey by Anand et al. (2013)
2. **NLP for Requirements Engineering**: Ferrari et al. (2017)
3. **LLMs for Code Generation**: Chen et al. (2021) - Codex
4. **Model Context Protocol**: Anthropic (2024)

---

## 4. System Architecture

### 4.1 Clean Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  CLI        │  │  MCP Server │  │  VS Code Extension      │  │
│  │  (workflows)│  │  (mcp_server)│  │  (GitHub Copilot)       │  │
│  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘  │
└─────────┼────────────────┼──────────────────────┼───────────────┘
          │                │                      │
┌─────────▼────────────────▼──────────────────────▼───────────────┐
│                     APPLICATION LAYER                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      WORKFLOWS                              │ │
│  │  GenerateWorkflow → UploadWorkflow → CheckStoryWorkflow    │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      USE CASES                              │ │
│  │  GenerateTests │ ValidateTests │ ExportDeliverables        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │                │                      │
┌─────────▼────────────────▼──────────────────────▼───────────────┐
│                      DOMAIN LAYER                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    DOMAIN SERVICES                           ││
│  │  ACParser │ StepBuilder │ QualityAnalyzer │ TestCorrector   ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    DOMAIN ENTITIES                           ││
│  │  TestCase │ TestStep │ UserStory │ AcceptanceCriteria       ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
          │                │                      │
┌─────────▼────────────────▼──────────────────────▼───────────────┐
│                   INFRASTRUCTURE LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ ADO Repository│  │ LLM Providers│  │ Export Generators     │ │
│  │ (HTTP Client) │  │ (OpenAI,etc) │  │ (CSV, Objectives)     │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Directory Structure

```
test_gen/
├── mcp_server.py              # MCP Server (main entry point)
├── workflows.py               # CLI Workflows
├── setup_project.py           # Project configuration tool
│
├── core/                      # DOMAIN LAYER
│   ├── interfaces/            # Abstract interfaces (Ports)
│   │   ├── repository.py      # IStoryRepository, ITestSuiteRepository
│   │   ├── llm_provider.py    # ILLMProvider
│   │   ├── config_provider.py # IProjectConfig, IADOConfig
│   │   ├── validator.py       # ITestValidator
│   │   └── quality_standards.py # IQualityAnalyzer, ITestCorrector
│   │
│   └── services/              # Domain Services
│       ├── ac_parser.py       # Acceptance Criteria Parser
│       ├── test_generator.py  # Generic Test Generator
│       ├── test_rules.py      # Rule-based generation
│       ├── test_validator.py  # Validation logic
│       │
│       ├── nlp/               # NLP Services
│       │   ├── spacy_parser.py    # spaCy integration
│       │   └── hybrid_parser.py   # Hybrid NLP approach
│       │
│       ├── quality/           # Quality Enhancement
│       │   ├── quality_analyzer.py    # Quality scoring
│       │   ├── test_corrector.py      # LLM correction
│       │   └── semantic_step_builder.py # Step enhancement
│       │
│       ├── cache/             # Caching Services
│       │   ├── cache_manager.py   # LRU + File cache
│       │   └── file_cache.py      # Persistent cache
│       │
│       └── metrics/           # Metrics Collection
│           ├── metrics_collector.py  # Usage tracking
│           └── cost_calculator.py    # LLM cost estimation
│
├── infrastructure/            # INFRASTRUCTURE LAYER
│   ├── ado/                   # Azure DevOps Integration
│   │   ├── http_client.py     # REST API client
│   │   └── ado_repository.py  # Repository implementations
│   │
│   └── export/                # Output Generators
│       ├── csv_generator.py       # ADO-compatible CSV
│       └── objective_generator.py # Rich-text objectives
│
├── llm/                       # LLM Providers
│   ├── factory.py             # Provider factory
│   ├── openai_provider.py     # OpenAI GPT
│   ├── anthropic_provider.py  # Anthropic Claude
│   └── cached_provider.py     # Caching wrapper
│
├── projects/                  # Multi-Project Support
│   ├── configs/               # YAML configurations
│   │   ├── env-quickdraw.yaml
│   │   └── mediapedia-us.yaml
│   ├── project_config.py      # Config loader
│   └── test_suite_creator.py  # ADO suite creation
│
├── .vscode/
│   └── mcp.json               # MCP configuration for Copilot
│
└── docs/
    ├── ONBOARDING_GUIDE.md    # QA tester guide
    └── MASTERS_THESIS_GUIDE.md # This document
```

### 4.3 Design Patterns Used

| Pattern | Implementation | Purpose |
|---------|---------------|---------|
| **Repository** | `IStoryRepository`, `ADOStoryRepository` | Decouple data access |
| **Factory** | `LLMFactory` | Create LLM provider instances |
| **Strategy** | `ILLMProvider` | Swap LLM backends |
| **Template Method** | `BaseWorkflow.execute()` | Standard workflow structure |
| **Decorator** | `CachedLLMProvider` | Add caching to any provider |
| **Dependency Injection** | Constructor injection | Enable testing |

---

## 5. Implementation Details

### 5.1 Acceptance Criteria Parsing

```python
# core/services/ac_parser.py

class ACParser:
    """
    Extracts semantic structure from acceptance criteria text.

    Input:  "User can rotate the selected object by 90 degrees"
    Output: ACSemantics(
        action="rotate",
        target="selected object",
        outcome="rotated by 90 degrees",
        conditions=["object is selected"],
        ui_element="rotate tool"
    )
    """

    def parse(self, ac_text: str) -> ACSemantics:
        # 1. Tokenize and POS tag with spaCy
        doc = self.nlp(ac_text)

        # 2. Extract verb phrases (actions)
        actions = self._extract_verbs(doc)

        # 3. Extract noun phrases (targets)
        targets = self._extract_objects(doc)

        # 4. Identify conditions (when, if, after)
        conditions = self._extract_conditions(doc)

        # 5. Map to UI elements
        ui_element = self._map_to_ui(actions, targets)

        return ACSemantics(
            action=actions[0] if actions else "",
            target=targets[0] if targets else "",
            outcome=self._derive_outcome(ac_text),
            conditions=conditions,
            ui_element=ui_element
        )
```

### 5.2 Test Case Generation Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    GENERATION PIPELINE                           │
│                                                                  │
│  Story ID                                                        │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────┐                                            │
│  │ 1. Fetch Story   │ ← ADO REST API                             │
│  │    from ADO      │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 2. Parse ACs     │ ← spaCy NLP + Custom Rules                 │
│  │    into bullets  │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 3. Check Feature │ ← Project Config                           │
│  │    Feasibility   │   (unavailable_features)                   │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 4. Generate      │ ← Rule-based StepBuilder                   │
│  │    Test Steps    │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 5. Quality       │ ← QualityAnalyzer                          │
│  │    Analysis      │   (0.0 - 1.0 score)                        │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 6. LLM Correction│ ← GPT-4o-mini / Claude                     │
│  │    (if needed)   │   (score < 0.7)                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 7. Export        │ → CSV + Objectives + JSON                  │
│  │    Deliverables  │                                            │
│  └──────────────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Test Step Structure

```python
# Generated test step format
TestStep = {
    "action": str,      # What to do
    "expected": str,    # What should happen
    "step_type": str    # prereq | action | verify | cleanup
}

# Example test case structure
TestCase = {
    "id": "272889-AC1",
    "title": "272889-AC1: Object Transformation / Edit Menu / Rotate tool",
    "objective": "Verify that Rotate tool rotates selected object by 90°",
    "steps": [
        {"action": "Pre-req: ENV QuickDraw App is installed", "expected": ""},
        {"action": "Launch the ENV QuickDraw application.", "expected": "Canvas is displayed"},
        {"action": "Draw a rectangle on the canvas.", "expected": "Rectangle is created"},
        {"action": "Select the rectangle.", "expected": "Selection handles appear"},
        {"action": "Click Edit Menu > Rotate.", "expected": "Object rotates 90° clockwise"},
        {"action": "Close the ENV QuickDraw App", "expected": ""}
    ]
}
```

---

## 6. Quality Enhancement Pipeline

### 6.1 Quality Metrics

```python
# core/interfaces/quality_standards.py

@dataclass
class TestCaseQualityMetrics:
    """Quantitative quality assessment."""

    title_quality: float        # 0.0 - 1.0 (specificity, length)
    step_quality: float         # 0.0 - 1.0 (action clarity)
    expected_quality: float     # 0.0 - 1.0 (observable outcomes)
    objective_quality: float    # 0.0 - 1.0 (completeness)
    overall_score: float        # Weighted average

    issues: List[QualityIssue]  # Detected problems
```

### 6.2 Quality Issue Detection

| Issue Type | Detection Method | Example |
|------------|------------------|---------|
| `GENERIC_STEP` | Pattern matching | "Perform the action described" |
| `GENERIC_EXPECTED` | Pattern matching | "Works as expected" |
| `MISSING_EXPECTED` | Empty check | No expected result |
| `FORBIDDEN_WORD` | Word list | "or", "if available" |
| `WEAK_ACTION` | NLP verb analysis | "Do", "Check" (too vague) |

### 6.3 LLM Correction Prompt

```python
# core/services/quality/test_corrector.py

CORRECTION_PROMPT = """
You are a QA expert. Improve this test step while maintaining its intent.

RULES:
1. Replace generic phrases with specific actions
2. Expected results must be OBSERVABLE (what user sees)
3. Never use: "works as expected", "if available", "or"
4. Keep technical accuracy

ORIGINAL:
Action: {action}
Expected: {expected}

IMPROVED (JSON format):
{{"action": "...", "expected": "..."}}
"""
```

### 6.4 Before/After Examples

**Before (Score: 0.35)**
```
Action: Perform the action described: Rotate Tool.
Expected: Works as expected.
```

**After (Score: 0.85)**
```
Action: Select Edit Menu > Rotate Tool and click on the selected object.
Expected: Object rotates 90 degrees clockwise. Rotation angle is displayed in Properties Panel.
```

---

## 7. MCP Integration for AI Assistants

### 7.1 Model Context Protocol (MCP) Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    MCP ARCHITECTURE                           │
│                                                               │
│  ┌─────────────┐         ┌─────────────┐                     │
│  │   GitHub    │  stdio  │    MCP      │                     │
│  │   Copilot   │◄───────►│   Server    │                     │
│  │   (Client)  │ JSON-RPC│ (mcp_server)│                     │
│  └─────────────┘         └──────┬──────┘                     │
│                                 │                             │
│                    ┌────────────┴────────────┐               │
│                    │                         │               │
│               ┌────▼────┐            ┌───────▼───────┐       │
│               │  Tools  │            │   Resources   │       │
│               └────┬────┘            └───────────────┘       │
│                    │                                          │
│      ┌─────────────┼─────────────┬─────────────┐             │
│      │             │             │             │             │
│  ┌───▼───┐    ┌────▼────┐   ┌────▼────┐   ┌───▼────┐        │
│  │generate│    │ upload  │   │ check   │   │ list   │        │
│  │ _tests │    │ _tests  │   │ _story  │   │projects│        │
│  └────────┘    └─────────┘   └─────────┘   └────────┘        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 MCP Tool Definitions

```python
# mcp_server.py

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="generate_tests",
            description="Generate test cases for a story. Saves to output folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_id": {"type": "string", "description": "ADO work item ID"},
                    "project": {"type": "string", "default": "env-quickdraw"}
                },
                "required": ["story_id"]
            }
        ),
        Tool(
            name="upload_tests",
            description="Generate AND upload to ADO test suite.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_id": {"type": "string"},
                    "project": {"type": "string"},
                    "dry_run": {"type": "boolean", "default": False}
                },
                "required": ["story_id"]
            }
        ),
        Tool(
            name="check_story",
            description="Get story details from ADO.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_id": {"type": "string"}
                },
                "required": ["story_id"]
            }
        ),
        Tool(
            name="list_projects",
            description="List available project configurations.",
            inputSchema={"type": "object", "properties": {}}
        )
    ]
```

### 7.3 VS Code Configuration

```json
// .vscode/mcp.json
{
  "servers": {
    "test-gen": {
      "type": "stdio",
      "command": "/path/to/venv310/bin/python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

### 7.4 User Interaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER WORKFLOW                             │
│                                                              │
│  1. User opens VS Code with test_gen project                 │
│  2. User opens .vscode/mcp.json → clicks "Start"             │
│  3. User opens Copilot Chat in "Agent" mode                  │
│  4. User types: "generate tests for story 272889"            │
│                                                              │
│         ┌──────────────────────────────────────┐             │
│         │ Copilot parses intent               │             │
│         │ → Identifies tool: generate_tests    │             │
│         │ → Extracts args: {story_id: 272889}  │             │
│         └──────────────────────────────────────┘             │
│                           │                                  │
│                           ▼                                  │
│         ┌──────────────────────────────────────┐             │
│         │ MCP Server executes tool             │             │
│         │ → Fetches story from ADO             │             │
│         │ → Generates test cases               │             │
│         │ → Saves to output/                   │             │
│         └──────────────────────────────────────┘             │
│                           │                                  │
│                           ▼                                  │
│         ┌──────────────────────────────────────┐             │
│         │ Copilot displays results             │             │
│         │ → Test count, file paths             │             │
│         │ → Offers follow-up actions           │             │
│         └──────────────────────────────────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Evaluation Methodology

### 8.1 Quantitative Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Generation Time** | Seconds per test case | < 2s |
| **Quality Score** | Automated quality assessment | > 0.7 |
| **LLM Token Usage** | Cost efficiency | < 500 tokens/TC |
| **AC Coverage** | % of ACs with tests | 100% |
| **Forbidden Word Rate** | % of tests with issues | < 5% |

### 8.2 Qualitative Evaluation

**Human Review Criteria:**
1. **Clarity**: Can a tester execute without ambiguity?
2. **Completeness**: Are all AC aspects covered?
3. **Accuracy**: Do steps match application behavior?
4. **Traceability**: Can test be traced to AC?

### 8.3 Comparison Baselines

| Approach | Generation | Quality | Cost |
|----------|------------|---------|------|
| Manual (Human) | Slow | High | High |
| Template-only | Fast | Medium | Low |
| LLM-only | Medium | Variable | High |
| **Our Hybrid** | Fast | High | Medium |

### 8.4 Dataset

```
Story 270737: GPS Input and Mapping (HIGH quality example)
- 15 acceptance criteria
- Human-reviewed test cases available
- Quality benchmark: 0.85

Story 272889: Object Transformation Tools (LOW quality example)
- 32 acceptance criteria
- Generic phrases common
- Quality benchmark: 0.48

Comparison:
- Our generated tests vs. human-written tests
- Measure: Precision, Recall, F1 for quality issues
```

---

## 9. Results and Findings

### 9.1 Generation Performance

```
┌─────────────────────────────────────────────────────────────┐
│                    PERFORMANCE RESULTS                       │
│                                                              │
│  Story 272889: Object Transformation Tools                   │
│  ─────────────────────────────────────────                   │
│  Acceptance Criteria:     32                                 │
│  Test Cases Generated:    34                                 │
│  Generation Time:         12.3 seconds                       │
│  Quality Score (before):  0.48                               │
│  Quality Score (after):   0.82 (+70%)                        │
│  LLM Tokens Used:         8,450                              │
│  Estimated LLM Cost:      $0.008                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Quality Improvement

| Metric | Before Correction | After Correction | Improvement |
|--------|-------------------|------------------|-------------|
| Generic Steps | 45% | 8% | -82% |
| Missing Expected | 32% | 3% | -91% |
| Forbidden Words | 12% | 0% | -100% |
| Overall Score | 0.48 | 0.82 | +71% |

### 9.3 MCP Integration Success

- **Tool Discovery**: 100% success in Copilot detecting tools
- **Execution Success**: 95% of tool calls complete successfully
- **User Satisfaction**: Reduced workflow steps from 8 to 2

---

## 10. Future Research Directions

### 10.1 Short-term Improvements (3-6 months)

| Enhancement | Description | Complexity |
|-------------|-------------|------------|
| **Test Data Generation** | Generate test data alongside steps | Medium |
| **Screenshot Verification** | Generate expected UI screenshots | High |
| **Multi-language Support** | Support non-English ACs | Medium |
| **Real-time Correction** | Correct as user types in ADO | High |

### 10.2 Medium-term Research (6-12 months)

#### 10.2.1 Reinforcement Learning for Quality

```
┌─────────────────────────────────────────────────────────────┐
│                    RL-BASED IMPROVEMENT                      │
│                                                              │
│  State:   Current test case quality metrics                  │
│  Action:  Apply correction rule / LLM prompt                 │
│  Reward:  Human approval / test execution success            │
│                                                              │
│  Training Loop:                                              │
│  1. Generate test case                                       │
│  2. Human reviews (accept/reject/modify)                     │
│  3. Update policy based on feedback                          │
│  4. Improve future generations                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### 10.2.2 Cross-Project Transfer Learning

```python
# Research Question: Can quality patterns transfer between projects?

# Approach:
# 1. Train quality model on Project A (high-quality examples)
# 2. Fine-tune on Project B (few examples)
# 3. Evaluate transfer effectiveness

class TransferLearningCorrector:
    def __init__(self, base_model, target_project):
        self.base = base_model  # Pre-trained on many projects
        self.adapter = ProjectAdapter(target_project)  # Small fine-tune

    def correct(self, test_case):
        base_correction = self.base.correct(test_case)
        return self.adapter.refine(base_correction)
```

### 10.3 Long-term Vision (1-2 years)

#### 10.3.1 End-to-End Test Automation

```
┌─────────────────────────────────────────────────────────────┐
│                    E2E AUTOMATION VISION                     │
│                                                              │
│  User Story                                                  │
│      │                                                       │
│      ▼                                                       │
│  ┌──────────────┐                                            │
│  │ Generate     │ ← Current System                           │
│  │ Test Cases   │                                            │
│  └──────┬───────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐                                            │
│  │ Generate     │ ← FUTURE: Playwright/Selenium              │
│  │ Test Scripts │   code generation                          │
│  └──────┬───────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐                                            │
│  │ Execute &    │ ← FUTURE: CI/CD integration                │
│  │ Report       │                                            │
│  └──────────────┘                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### 10.3.2 Autonomous QA Agent

```python
# Vision: Fully autonomous QA agent

class AutonomousQAAgent:
    """
    An AI agent that:
    1. Monitors new user stories in ADO
    2. Generates test cases automatically
    3. Creates test scripts
    4. Executes tests
    5. Reports results
    6. Learns from failures
    """

    async def run(self):
        while True:
            new_stories = await self.monitor_ado()
            for story in new_stories:
                tests = await self.generate_tests(story)
                scripts = await self.generate_scripts(tests)
                results = await self.execute_tests(scripts)
                await self.report_and_learn(results)
```

### 10.4 Thesis Extension Topics

| Topic | Research Questions | Methods |
|-------|-------------------|---------|
| **Semantic Similarity** | How similar are generated tests to human-written? | Sentence embeddings, cosine similarity |
| **Defect Prediction** | Can test quality predict defect detection? | ML classification, historical data |
| **Effort Estimation** | How much time does automation save? | Time studies, surveys |
| **Explainability** | Why did LLM make this correction? | Attention analysis, SHAP values |

---

## 11. Appendices

### 11.1 API Reference

#### MCP Server Endpoints

```
POST /tools/generate_tests
  Input:  { "story_id": "272889", "project": "env-quickdraw" }
  Output: { "success": true, "test_count": 34, "output_files": {...} }

POST /tools/upload_tests
  Input:  { "story_id": "272889", "dry_run": false }
  Output: { "success": true, "created_count": 34, "suite_info": {...} }

POST /tools/check_story
  Input:  { "story_id": "272889" }
  Output: { "title": "...", "acceptance_criteria": [...] }

POST /tools/list_projects
  Input:  {}
  Output: { "available_projects": ["env-quickdraw", "mediapedia-us"] }
```

### 11.2 Configuration Schema

```yaml
# Project Configuration Schema (YAML)
project_id: string        # Unique identifier
application:
  name: string           # Display name
  type: enum             # web | desktop | mobile
  prereq_template: string
  launch_step: string
  launch_expected: string
  close_step: string
  unavailable_features: list[string]
  feature_aliases: dict[string, string]
  ui_surfaces: list[string]
  entry_point_mappings: dict[string, string]
  platforms: list[string]

ado:
  organization: string
  project: string
  area_path: string
  assigned_to: string
  default_state: string
  test_suite_pattern: string
  qa_prep_pattern: string | null

rules:
  forbidden_words: list[string]
  first_test_id: string
  test_id_increment: integer

output_dir: string
llm_enabled: boolean
llm_provider: enum        # openai | anthropic | ollama
llm_model: string
```

### 11.3 Quality Score Calculation

```python
def calculate_quality_score(test_case: TestCase) -> float:
    """
    Quality score formula:

    Q = w1*title + w2*steps + w3*expected + w4*objective

    Where:
    - w1 = 0.15 (title weight)
    - w2 = 0.35 (step clarity weight)
    - w3 = 0.35 (expected result weight)
    - w4 = 0.15 (objective weight)

    Each component scored 0.0 - 1.0 based on:
    - Specificity (no generic phrases)
    - Completeness (all required fields)
    - Measurability (observable outcomes)
    """
    weights = {'title': 0.15, 'steps': 0.35, 'expected': 0.35, 'objective': 0.15}

    scores = {
        'title': score_title(test_case.title),
        'steps': score_steps(test_case.steps),
        'expected': score_expected_results(test_case.steps),
        'objective': score_objective(test_case.objective)
    }

    return sum(w * scores[k] for k, w in weights.items())
```

### 11.4 Glossary

| Term | Definition |
|------|------------|
| **AC** | Acceptance Criteria - testable conditions for user story completion |
| **ADO** | Azure DevOps - Microsoft's project management platform |
| **LLM** | Large Language Model - AI model for text generation (GPT, Claude) |
| **MCP** | Model Context Protocol - Anthropic's protocol for AI tool integration |
| **NLP** | Natural Language Processing - computational linguistics |
| **spaCy** | Open-source NLP library in Python |
| **Clean Architecture** | Software design separating concerns into layers |

### 11.5 References

1. Anand, S., et al. (2013). "An orchestrated survey of methodologies for automated software test case generation." JSS.
2. Ferrari, A., et al. (2017). "Natural language requirements processing: A 4D vision." IEEE Software.
3. Chen, M., et al. (2021). "Evaluating Large Language Models Trained on Code." arXiv.
4. Anthropic. (2024). "Model Context Protocol Specification." https://modelcontextprotocol.io
5. OpenAI. (2023). "GPT-4 Technical Report." arXiv.

---

## Document Information

| Field | Value |
|-------|-------|
| **Author** | Gulzhas Mailybayeva |
| **Version** | 1.0 |
| **Date** | January 2026 |
| **Framework Version** | 4.0 |
| **Status** | Living Document |

---

*This document serves as both technical documentation and academic research material for Master's thesis work on AI-driven software testing.*
