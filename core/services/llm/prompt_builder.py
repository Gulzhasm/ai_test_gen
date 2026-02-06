#!/usr/bin/env python3
"""
Dynamic Prompt Builder for Project-Agnostic Test Generation

Contract-first, token-efficient prompt architecture:
- SYSTEM prompt: Short, stable role + output contract + rule priority + universal rules
- USER prompt: Structured story metadata + scope + test plan spec + constraints + seeds

All preprocessing (AC cleaning, scope filtering, truncation) is done deterministically
in code before sending to LLM.
"""
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
import re
import json


# =============================================================================
# FEATURE TYPE DETECTION (Multi-label support)
# =============================================================================

FEATURE_TYPE_PATTERNS = {
    'input': [
        r'\binput', r'\benter', r'\btype\b', r'\bfield\b', r'\bform\b',
        r'\btextbox', r'\bdropdown', r'\bselect\b.*\bvalue\b', r'\bset\b.*\bvalue\b',
        r'\bedit\b.*\bvalue\b', r'\bchange\b.*\bvalue\b', r'\bmodify\b.*\bvalue\b',
        r'\bcoordinat', r'\blatitud', r'\blongitud', r'\btext\s+(?:box|field)',
        r'\bfill\s+in\b', r'\bprovid', r'\bspecif'
    ],
    'calculation': [
        r'\bcalculat', r'\bcomput', r'\bsum\b', r'\btotal', r'\bformula',
        r'\bconvert', r'\bmeasur', r'\bdimension', r'\bvalue\b.*\bdisplay',
        r'\bresult', r'\bmath', r'\barithmetic'
    ],
    'navigation': [
        r'\bmenu\b', r'\bnavigate', r'\bopen\b', r'\bclose\b', r'\baccess',
        r'\bhelp\b', r'\babout\b', r'\bmanual\b', r'\bguide\b', r'\bdocument',
        r'\bfile\s+menu', r'\bedit\s+menu', r'\btools?\s+menu', r'\bview\s+menu'
    ],
    'display': [
        r'\bview(?:er)?\b', r'\bdisplay', r'\bshow', r'\bappear', r'\bvisible',
        r'\bread\b', r'\bpdf\b', r'\bimage\b', r'\breport', r'\bpreview',
        r'\bread-only', r'\bsee\b', r'\bwatch'
    ],
    'object_manipulation': [
        r'\brotat', r'\bmov(?:e|es|ed|ing)\b', r'\bresiz', r'\bscal', r'\bflip',
        r'\bmirror', r'\bduplic', r'\bcopy', r'\bpaste', r'\bdelet',
        r'\bdraw', r'\bcreate\b.*\bobject', r'\bshape\b', r'\btool\b',
        r'\btransform', r'\breposition', r'\bselect\b.*\bobject'
    ]
}

# Minimum score threshold to include a feature type
FEATURE_TYPE_MIN_SCORE = 2


def detect_feature_types(feature_name: str, acceptance_criteria: List[str]) -> List[str]:
    """
    Detect feature types as a MULTI-LABEL list.

    Returns list of matching types sorted by score (highest first).
    Returns ['general'] if no patterns match.
    """
    combined_text = f"{feature_name} {' '.join(acceptance_criteria)}".lower()

    scores = {}
    for feature_type, patterns in FEATURE_TYPE_PATTERNS.items():
        score = sum(1 for pattern in patterns if re.search(pattern, combined_text, re.IGNORECASE))
        if score >= FEATURE_TYPE_MIN_SCORE:
            scores[feature_type] = score

    if not scores:
        return ['general']

    # Sort by score descending
    sorted_types = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)
    return sorted_types


def detect_feature_type(feature_name: str, acceptance_criteria: List[str]) -> str:
    """
    Backward-compatible single-label detection.
    Returns the primary (highest-scoring) feature type.
    """
    types = detect_feature_types(feature_name, acceptance_criteria)
    return types[0] if types else 'general'


# =============================================================================
# DETERMINISTIC PREPROCESSING HELPERS
# =============================================================================

# Patterns to identify header bullets that should be removed
AC_HEADER_PATTERNS = [
    r'^acceptance\s+criteria:?\s*$',
    r'^ac:?\s*$',
    r'^criteria:?\s*$',
    r'^requirements?:?\s*$',
    r'^definition\s+of\s+done:?\s*$',
    r'^dod:?\s*$',
]

# Patterns to identify out-of-scope markers
OUT_OF_SCOPE_PATTERNS = [
    r'^\[out[- ]?of[- ]?scope\]',
    r'^out[- ]?of[- ]?scope:',
    r'^\[excluded\]',
    r'^\[not\s+in\s+scope\]',
    r'^excluded:',
    r'^\[deferred\]',
    r'^deferred:',
]

# Placeholder patterns to lint from seed tests
SEED_LINT_PATTERNS = [
    r'\bverify\s+functionality\b',
    r'\be\.?g\.?,?\s+',
    r'\bif\s+available\b',
    r'\bif\s+supported\b',
    r'\b(?:X|Y)\s+or\s+(?:X|Y)\b',
    r'<placeholder>',
    r'\[TBD\]',
    r'\[TODO\]',
]

# HTML tags to strip from seed tests
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

# Entity extraction patterns for boundary-bearing entities
ENTITY_PATTERNS = {
    'file_input': [r'\bfile\b', r'\bpicker\b', r'\bbrowse\b', r'\bformat\b', r'\bimport\b', r'\bexport\b', r'\bopen\b'],
    'insertion_workflow': [r'\binsert\b', r'\bcreate\b', r'\badd\b', r'\bnew\b'],
    'object_transform': [r'\bmove\b', r'\bresize\b', r'\brotat', r'\block\b', r'\bdrag\b', r'\bflip\b', r'\bmirror\b', r'\bscal'],
    'text_input': [r'\btext\b', r'\btype\b', r'\beditable\b', r'\bkeyboard\b', r'\binput\b', r'\benter\b'],
    'annotation': [r'\bannotation\b', r'\bcomment\b', r'\bmarker\b', r'\bnote\b', r'\blabel\b'],
    'overlay_visibility': [r'\bvisible\b', r'\bhide\b', r'\boverlay\b', r'\btop\s+layer\b', r'\bcannot\s+be\s+covered\b', r'\bz-order\b'],
    'selection': [r'\bselect\b', r'\bhighlight\b', r'\bfocus\b', r'\bactive\b'],
    'state_change': [r'\bundo\b', r'\bredo\b', r'\bsave\b', r'\brevert\b', r'\brestore\b'],
}

# =============================================================================
# COMPREHENSIVE WORKFLOW PATTERNS
# =============================================================================

# Step sequences for entity types - LLM should include ALL steps when entity is present
COMPREHENSIVE_WORKFLOW_STEPS = {
    'inserted_object': [
        'Insert/place object on canvas',
        'Move object to different location',
        'Resize object (maintain aspect ratio)',
        'Rotate object',
        'Lock object as background (if applicable)',
    ],
    'image_file': [
        'Open file picker',
        'Select file from picker',
        'Verify object appears centered on canvas',
        'Move to different location',
        'Resize while maintaining aspect ratio',
        'Rotate by 90 degrees',
        'Lock as background',
    ],
    'text_field': [
        'Insert text field',
        'Enter text content',
        'Move text field',
        'Edit text content',
        'Delete text field',
    ],
    'annotation': [
        'Insert annotation',
        'Enter annotation content',
        'Move annotation marker',
        'Edit annotation content',
        'Delete annotation',
    ],
    'overlay_indicator': [
        'Verify indicator is visible',
        'Attempt to cover with other objects',
        'Hide indicator',
        'Unhide indicator',
    ],
}

# Format variations for file inputs - generate separate test per format
FORMAT_VARIATIONS = {
    'image': ['PNG', 'JPG', 'BMP'],
    'document': ['PDF', 'DOCX', 'TXT'],
    'drawing': ['DWG', 'DXF', 'SVG'],
    'data': ['CSV', 'JSON', 'XML'],
}

# Entity-to-workflow mapping
ENTITY_WORKFLOW_MAP = {
    'file_input': 'image_file',
    'insertion_workflow': 'inserted_object',
    'object_transform': 'inserted_object',
    'text_input': 'text_field',
    'annotation': 'annotation',
    'overlay_visibility': 'overlay_indicator',
}

# Areas that are informational and should NOT have boundary tests unless explicitly referenced
INFORMATIONAL_AREAS = [
    'Help Menu', 'About', 'Legal', 'Release Notes', 'Documentation',
    'Manual', 'Guide', 'License', 'Credits', 'Version Info'
]


# =============================================================================
# COMPLEXITY-BASED TEST COUNT CALCULATION
# =============================================================================

@dataclass
class TestRequirements:
    """Calculated test requirements based on story complexity."""
    min_total: int
    max_total: int
    min_core: int
    min_negative: int
    min_edge: int
    min_state: int
    min_accessibility: int
    complexity_score: float
    complexity_factors: Dict[str, Any]


def calculate_test_requirements(
    ac_count: int,
    feature_types: List[str],
    boundary_entities: List[str],
    comprehensive_workflows: Dict[str, List[str]],
    format_variations: Dict[str, List[str]],
    platform_count: int,
    qa_prep: str = ""
) -> TestRequirements:
    """
    Calculate test requirements based on story complexity.

    Simple formula:
    - min_total = AC count + platform count (accessibility)
    - Edge/negative/state are RECOMMENDED but NOT counted in minimum

    This ensures the LLM covers all ACs and adds accessibility tests,
    but doesn't force artificial inflation of test counts.

    Returns TestRequirements with calculated minimums.
    """
    complexity_factors = {}

    # =========================================================================
    # BASE: Core tests = AC count (cover every AC)
    # =========================================================================
    min_core = ac_count
    complexity_factors['ac_count'] = ac_count

    # =========================================================================
    # ACCESSIBILITY: 1 per platform (always required)
    # =========================================================================
    min_accessibility = platform_count
    complexity_factors['platforms'] = platform_count

    # =========================================================================
    # DETERMINE COMPLEXITY LEVEL (for recommendations, not minimums)
    # =========================================================================
    high_complexity_types = {'input', 'object_manipulation', 'calculation'}
    primary_type = feature_types[0] if feature_types else 'general'
    is_complex = primary_type in high_complexity_types

    complexity_factors['feature_type'] = primary_type
    complexity_factors['is_complex'] = is_complex

    # =========================================================================
    # EDGE/NEGATIVE/STATE: Recommended but NOT mandatory
    # These are tracked for prompt guidance but don't add to min_total
    # =========================================================================
    if is_complex:
        # Recommendations for complex features
        min_negative = 1  # Recommended
        min_edge = 1      # Recommended
        has_state_entity = 'state_change' in boundary_entities
        min_state = 1 if has_state_entity else 0
        complexity_score = 0.5
    else:
        min_negative = 0
        min_edge = 0
        min_state = 0
        complexity_score = 0.2

    # Format variations are recommendations
    format_count = sum(len(formats) for formats in format_variations.values())
    if format_count > 0:
        complexity_factors['format_variations'] = format_count

    # =========================================================================
    # TOTAL: Just core + accessibility (edge/negative are bonus)
    # =========================================================================
    min_total = min_core + min_accessibility

    # Max allows room for edge/negative/state if LLM adds them
    max_total = min_total + 10

    complexity_factors['breakdown'] = f"core:{min_core} + a11y:{min_accessibility} = {min_total} (edge/neg/state recommended but optional)"

    return TestRequirements(
        min_total=min_total,
        max_total=max_total,
        min_core=min_core,
        min_negative=min_negative,
        min_edge=min_edge,
        min_state=min_state,
        min_accessibility=min_accessibility,
        complexity_score=complexity_score,
        complexity_factors=complexity_factors
    )

# Core interaction areas that can have boundary tests
CORE_INTERACTION_AREAS = [
    'Canvas', 'Dialog Window', 'Modal Window', 'Insert Menu', 'File Menu',
    'Edit Menu', 'Tools Menu', 'View Menu', 'Properties Panel', 'Dimensions Panel'
]


def extract_boundary_entities(in_scope_acs: List[str]) -> List[str]:
    """
    Extract boundary-bearing entities from in-scope ACs.
    These are the only entities that can have edge/negative/boundary tests.
    """
    combined_text = ' '.join(in_scope_acs).lower()
    entities = []

    for entity, patterns in ENTITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                entities.append(entity)
                break

    # Dedupe and return
    return list(dict.fromkeys(entities)) if entities else ['in_scope_workflow']


def derive_edge_allowed_areas(allowed_areas: List[str], in_scope_acs: List[str]) -> Tuple[List[str], List[str]]:
    """
    Determine which areas can have edge/boundary tests.

    Returns:
        Tuple of (edge_allowed_areas, edge_disallowed_areas)
    """
    combined_text = ' '.join(in_scope_acs).lower()
    edge_allowed = []
    edge_disallowed = []

    for area in allowed_areas:
        area_lower = area.lower()

        # Check if it's an informational area
        is_informational = any(info.lower() in area_lower for info in INFORMATIONAL_AREAS)

        # Check if it's a core interaction area
        is_core = any(core.lower() in area_lower for core in CORE_INTERACTION_AREAS)

        # Check if area is referenced in ACs
        is_referenced = area_lower.replace(' ', '') in combined_text.replace(' ', '') or \
                       any(word in combined_text for word in area_lower.split() if len(word) > 3)

        if is_informational and not is_referenced:
            edge_disallowed.append(area)
        elif is_core or is_referenced:
            edge_allowed.append(area)
        else:
            edge_allowed.append(area)  # Default to allowed if not clearly informational

    return edge_allowed, edge_disallowed


def detect_format_variations(in_scope_acs: List[str]) -> Dict[str, List[str]]:
    """
    Detect if format variations should be tested based on ACs.

    Only triggers when ACs EXPLICITLY mention specific formats (PNG, JPG, etc.)
    or explicitly state multiple format support.

    Returns dict mapping format category to list of formats to test.
    E.g., {'image': ['PNG', 'JPG', 'BMP']} if multiple image formats are in scope.
    """
    combined_text = ' '.join(in_scope_acs).lower()
    variations = {}

    # Image format detection - REQUIRE explicit format mentions or "multiple formats"
    image_format_patterns = [r'\bpng\b', r'\bjpg\b', r'\bjpeg\b', r'\bbmp\b', r'\btiff\b', r'\bgif\b']
    explicit_formats_found = sum(1 for p in image_format_patterns if re.search(p, combined_text))

    # Only add image variations if:
    # 1. Multiple explicit formats mentioned, OR
    # 2. AC explicitly says "multiple formats" or "various formats"
    if explicit_formats_found >= 2 or re.search(r'\b(?:multiple|various|different)\s+(?:image\s+)?formats?\b', combined_text):
        variations['image'] = FORMAT_VARIATIONS['image']

    # Document format detection - require explicit format mentions
    doc_format_patterns = [r'\bpdf\b', r'\bdocx?\b', r'\btxt\b', r'\brtf\b']
    doc_formats_found = sum(1 for p in doc_format_patterns if re.search(p, combined_text))
    if doc_formats_found >= 2 or re.search(r'\b(?:multiple|various)\s+(?:document\s+)?formats?\b', combined_text):
        variations['document'] = FORMAT_VARIATIONS['document']

    # Drawing format detection - require explicit format mentions
    drawing_format_patterns = [r'\bdwg\b', r'\bdxf\b', r'\bsvg\b']
    drawing_formats_found = sum(1 for p in drawing_format_patterns if re.search(p, combined_text))
    if drawing_formats_found >= 2:
        variations['drawing'] = FORMAT_VARIATIONS['drawing']

    return variations


def extract_comprehensive_workflows(boundary_entities: List[str], in_scope_acs: List[str]) -> Dict[str, List[str]]:
    """
    Extract comprehensive workflow step requirements based on detected entities.

    Only includes workflows when the ACs explicitly describe insertion/creation actions.
    Transform-only stories (rotate, mirror, flip) should NOT get insertion workflows.

    Returns dict mapping workflow type to list of steps that MUST be included.
    """
    workflows = {}
    combined_text = ' '.join(in_scope_acs).lower()

    # Only trigger insertion workflows if ACs explicitly mention insertion/creation
    insertion_patterns = [r'\binsert\b', r'\badd\s+(?:new|a|an)\b', r'\bcreate\s+(?:new|a|an)\b', r'\bplace\s+(?:new|a|an)\b']
    has_insertion_context = any(re.search(p, combined_text) for p in insertion_patterns)

    for entity in boundary_entities:
        workflow_type = ENTITY_WORKFLOW_MAP.get(entity)
        if workflow_type and workflow_type in COMPREHENSIVE_WORKFLOW_STEPS:
            # Skip insertion/object workflows if no insertion context in ACs
            if workflow_type in ('inserted_object', 'image_file') and not has_insertion_context:
                continue
            # Skip text_field workflow unless explicitly creating text fields
            if workflow_type == 'text_field' and not re.search(r'\b(?:insert|add|create)\s+(?:text|editable)\b', combined_text):
                continue
            workflows[workflow_type] = COMPREHENSIVE_WORKFLOW_STEPS[workflow_type]

    # Additional workflow detection from AC text
    # Detect visibility/indicator patterns
    visibility_patterns = [r'\bvisible\b', r'\bhide\b', r'\bunhide\b', r'\bshow\b', r'\btop\s+layer\b', r'\bindicator\b']
    if any(re.search(p, combined_text) for p in visibility_patterns):
        if 'overlay_indicator' not in workflows:
            workflows['overlay_indicator'] = COMPREHENSIVE_WORKFLOW_STEPS['overlay_indicator']

    # Detect text/editable field patterns
    text_patterns = [r'\beditable\b', r'\btext\s+field\b', r'\btype\b.*\btext\b', r'\bedit\b.*\btext\b']
    if any(re.search(p, combined_text) for p in text_patterns):
        if 'text_field' not in workflows:
            workflows['text_field'] = COMPREHENSIVE_WORKFLOW_STEPS['text_field']

    return workflows


def clean_acceptance_criteria(raw_acs: List[str]) -> List[str]:
    """
    Clean acceptance criteria deterministically:
    - Strip header bullets like "Acceptance Criteria"
    - Trim whitespace
    - Remove empty bullets
    - Deduplicate while preserving order
    """
    cleaned = []
    seen = set()

    for ac in raw_acs:
        # Trim whitespace
        ac = ac.strip()

        # Skip empty
        if not ac:
            continue

        # Skip header bullets
        ac_lower = ac.lower()
        is_header = any(re.match(pattern, ac_lower) for pattern in AC_HEADER_PATTERNS)
        if is_header:
            continue

        # Remove leading bullet characters
        ac = re.sub(r'^[\-\*•◦▪]\s*', '', ac)
        ac = re.sub(r'^\d+[\.\)]\s*', '', ac)
        ac = ac.strip()

        if not ac:
            continue

        # Deduplicate (case-insensitive)
        ac_normalized = ac_lower.strip()
        if ac_normalized in seen:
            continue
        seen.add(ac_normalized)

        cleaned.append(ac)

    return cleaned


def filter_contradictory_unsupported(unsupported_features: List[str], in_scope_acs: List[str]) -> List[str]:
    """
    Filter out unsupported features that contradict the in-scope ACs.

    If an AC explicitly mentions a capability (e.g., "multi-selected objects transform together"),
    we should NOT list that capability as unsupported.

    Returns filtered list of unsupported features.
    """
    combined_acs = ' '.join(in_scope_acs).lower()
    filtered = []

    for feature in unsupported_features:
        feature_lower = feature.lower()
        # Extract key terms from the feature name
        key_terms = re.findall(r'\b\w+\b', feature_lower)

        # Check if this feature is actually mentioned positively in the ACs
        is_contradicted = False
        for term in key_terms:
            if len(term) > 3:  # Skip short words like "the", "and"
                # Check if the term appears in a positive context in ACs
                if re.search(rf'\b{re.escape(term)}\b', combined_acs):
                    is_contradicted = True
                    break

        if not is_contradicted:
            filtered.append(feature)

    return filtered


def split_scope(acs: List[str]) -> Tuple[List[str], List[str]]:
    """
    Split acceptance criteria into in-scope and out-of-scope.

    Returns:
        Tuple of (in_scope_acs, out_of_scope_acs)
    """
    in_scope = []
    out_of_scope = []

    for ac in acs:
        ac_lower = ac.lower().strip()

        # Check if marked as out of scope
        is_out_of_scope = any(
            re.match(pattern, ac_lower, re.IGNORECASE)
            for pattern in OUT_OF_SCOPE_PATTERNS
        )

        if is_out_of_scope:
            # Clean the marker from the AC text
            cleaned_ac = ac
            for pattern in OUT_OF_SCOPE_PATTERNS:
                cleaned_ac = re.sub(pattern, '', cleaned_ac, flags=re.IGNORECASE).strip()
            if cleaned_ac:
                out_of_scope.append(cleaned_ac)
        else:
            in_scope.append(ac)

    return in_scope, out_of_scope


def safe_truncate(text: str, max_chars: int) -> str:
    """
    Truncate text at sentence boundary, never mid-word.
    Appends "…[truncated]" when truncation occurs.
    """
    if not text or len(text) <= max_chars:
        return text

    # Find a good truncation point
    truncate_at = max_chars - 15  # Leave room for "…[truncated]"

    if truncate_at <= 0:
        return "…[truncated]"

    # Try to find sentence boundary
    sentence_ends = ['.', '!', '?', '\n']
    best_pos = -1

    for i in range(min(truncate_at, len(text) - 1), max(0, truncate_at - 200), -1):
        if text[i] in sentence_ends:
            best_pos = i + 1
            break

    # If no sentence boundary, find word boundary (look for space BEFORE the word)
    if best_pos == -1:
        # Find the last complete word by looking for space
        for i in range(min(truncate_at, len(text) - 1), max(0, truncate_at - 100), -1):
            if text[i] in ' \t\n':
                best_pos = i  # Stop at the space
                break

    # Fallback to hard truncate (but walk back to word boundary)
    if best_pos == -1:
        best_pos = min(truncate_at, len(text))
        while best_pos > 0 and text[best_pos - 1].isalnum():
            best_pos -= 1

    # Ensure we have something to return
    if best_pos <= 0:
        best_pos = min(truncate_at, len(text))

    return text[:best_pos].rstrip() + "…[truncated]"


def lint_seed_test(test_case: Dict) -> Dict:
    """
    Remove obvious placeholders and HTML tags from seed test case text.
    Returns cleaned test case with minimal fields for output contract.
    """
    def clean_text(text: str) -> str:
        if not text:
            return text
        # Strip HTML tags first
        text = HTML_TAG_PATTERN.sub('', text)
        # Remove placeholder patterns
        for pattern in SEED_LINT_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text.strip()

    # Extract only fields required by output contract
    cleaned = {
        'id': test_case.get('id', ''),
        'title': clean_text(test_case.get('title', '')),
        'objective': clean_text(test_case.get('objective', '')),
    }

    # Minimal steps: only action and expected
    if 'steps' in test_case:
        cleaned['steps'] = [
            {
                'action': clean_text(step.get('action', '')),
                'expected': clean_text(step.get('expected', ''))
            }
            for step in test_case.get('steps', [])
        ]

    return cleaned


def reduce_seed_tests(test_cases: List[Dict], max_size: int = 8000) -> List[Dict]:
    """
    Reduce seed tests to fit within token budget.
    Keeps only essential fields and limits count if needed.
    """
    # First, lint all tests
    linted = [lint_seed_test(tc) for tc in test_cases]

    # Check size
    current_json = json.dumps(linted, indent=2)
    if len(current_json) <= max_size:
        return linted

    # Reduce by removing tests until under limit
    while len(linted) > 3 and len(json.dumps(linted, indent=2)) > max_size:
        linted.pop()

    return linted


# =============================================================================
# PROMPT CONTEXT
# =============================================================================

@dataclass
class PromptContext:
    """Context for building dynamic prompts."""
    app_name: str
    app_type: str  # desktop, web, mobile, hybrid
    story_id: str
    feature_name: str
    acceptance_criteria: List[str]  # Raw ACs (cleaned externally)
    qa_prep: str

    # Application constraints
    unavailable_features: List[str]
    feature_notes: Dict[str, str]

    # UI configuration
    ui_surfaces: List[str]
    entry_points: Dict[str, str]

    # Platform support
    platforms: List[str]

    # Step templates
    prereq_template: str
    launch_step: str
    launch_expected: str
    create_file_step: str
    create_file_expected: str
    close_step: str

    # Test rules
    forbidden_words: List[str]
    allowed_areas: List[str]

    # NEW: Preprocessed fields (populated by PromptBuilder)
    acceptance_criteria_in_scope: List[str] = field(default_factory=list)
    acceptance_criteria_out_of_scope: List[str] = field(default_factory=list)
    feature_types: List[str] = field(default_factory=list)
    boundary_entities: List[str] = field(default_factory=list)
    edge_allowed_areas: List[str] = field(default_factory=list)
    edge_disallowed_areas: List[str] = field(default_factory=list)

    # Comprehensive test generation fields
    format_variations: Dict[str, List[str]] = field(default_factory=dict)
    comprehensive_workflows: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def feature_type(self) -> str:
        """Primary feature type (backward compatible)."""
        if self.feature_types:
            return self.feature_types[0]
        return detect_feature_type(self.feature_name, self.acceptance_criteria)

    @property
    def primary_feature_type(self) -> str:
        """Alias for feature_type."""
        return self.feature_type


# =============================================================================
# OUTPUT CONTRACT (JSON Schema)
# =============================================================================

OUTPUT_SCHEMA = {
    "test_cases": [
        {
            "id": "string (format: {story_id}-{sequence})",
            "title": "string (format: {story_id}-{id}: {Feature} / {Area} / {Scenario})",
            "objective": "string (starts with 'Verify that')",
            "steps": [
                {"step": "number (start at 1)", "action": "string", "expected": "string or empty"}
            ]
        }
    ]
}


# =============================================================================
# PROMPT BUILDER
# =============================================================================

class PromptBuilder:
    """
    Builds contract-first, token-efficient prompts for LLM test generation.

    Architecture:
    - SYSTEM prompt: ~1-2KB, stable role + output contract + rule priority
    - USER prompt: Structured sections with story-specific data
    """

    def __init__(self, context: PromptContext):
        self.ctx = context
        self._preprocess_context()

    def _preprocess_context(self):
        """Run deterministic preprocessing on context data."""
        # Clean and split ACs
        cleaned_acs = clean_acceptance_criteria(self.ctx.acceptance_criteria)
        in_scope, out_of_scope = split_scope(cleaned_acs)

        self.ctx.acceptance_criteria_in_scope = in_scope
        self.ctx.acceptance_criteria_out_of_scope = out_of_scope

        # Filter out unsupported features that contradict in-scope ACs
        # (e.g., if AC says "multi-selected objects transform together",
        # don't list "multi-select" as unsupported)
        self.ctx.unavailable_features = filter_contradictory_unsupported(
            self.ctx.unavailable_features,
            in_scope
        )

        # Multi-label feature detection
        self.ctx.feature_types = detect_feature_types(
            self.ctx.feature_name,
            in_scope  # Use in-scope ACs for detection
        )

        # Extract boundary-bearing entities
        self.ctx.boundary_entities = extract_boundary_entities(in_scope)

        # Derive edge-allowed areas
        edge_allowed, edge_disallowed = derive_edge_allowed_areas(
            self.ctx.allowed_areas,
            in_scope
        )
        self.ctx.edge_allowed_areas = edge_allowed
        self.ctx.edge_disallowed_areas = edge_disallowed

        # Detect format variations for comprehensive coverage
        self.ctx.format_variations = detect_format_variations(in_scope)

        # Extract comprehensive workflow requirements
        self.ctx.comprehensive_workflows = extract_comprehensive_workflows(
            self.ctx.boundary_entities,
            in_scope
        )

        # Truncate QA prep
        if self.ctx.qa_prep:
            self.ctx.qa_prep = safe_truncate(self.ctx.qa_prep, 2000)

    @classmethod
    def from_project_config(
        cls,
        config,  # ProjectConfig
        story_id: str,
        feature_name: str,
        acceptance_criteria: List[str],
        qa_prep: str = ""
    ) -> 'PromptBuilder':
        """Create PromptBuilder from a ProjectConfig."""
        context = PromptContext(
            app_name=config.application.name,
            app_type=config.application.app_type,
            story_id=story_id,
            feature_name=feature_name,
            acceptance_criteria=acceptance_criteria,
            qa_prep=qa_prep,
            unavailable_features=getattr(config.application, 'unavailable_features', []),
            feature_notes=getattr(config.application, 'feature_notes', {}),
            ui_surfaces=config.application.main_ui_surfaces,
            entry_points=config.application.entry_point_mappings,
            platforms=config.application.supported_platforms,
            prereq_template=config.application.prereq_template,
            launch_step=config.application.launch_step,
            launch_expected=config.application.launch_expected or "",
            create_file_step=getattr(config.application, 'create_file_step', 'Create a new file/document.'),
            create_file_expected=getattr(config.application, 'create_file_expected', 'A new blank file is created.'),
            close_step=config.application.close_step,
            forbidden_words=config.rules.forbidden_words,
            allowed_areas=config.rules.allowed_areas,
        )
        return cls(context)

    def build_system_prompt(self) -> str:
        """
        Build system prompt with expert QA mindset.

        This prompt guides the LLM to think like a senior QA engineer who:
        - Derives implicit test scenarios from AC text
        - Creates negative tests from exclusion statements
        - Builds workflow tests that verify state persistence
        - Writes specific, concrete steps (never generic)
        """
        return f'''You are a SENIOR QA ENGINEER who writes expert-level test cases. Output JSON only.

## YOUR MINDSET
Think like an expert QA whose goal is to FIND BUGS, not just confirm functionality works.
For EVERY acceptance criterion, ask yourself:
1. What's the POSITIVE case? (verify it works)
2. What's the NEGATIVE case? (verify incorrect states are handled)
3. What EDGE CASES exist? (boundaries, empty states, max values)
4. What WORKFLOW tests verify STATE PERSISTENCE? (create → verify → create again)
5. What's IMPLIED but not stated? (if "modal dialog", test focus trapping)

## OUTPUT CONTRACT
Return ONLY valid JSON matching this schema:
{json.dumps(OUTPUT_SCHEMA, indent=2)}

No markdown. No commentary. No extra keys. No HTML tags.

## EXPERT QA RULES (Critical)

### 1. DERIVE NEGATIVE TESTS FROM EXCLUSIONS
When AC says "X is out of scope" or "only Y":
- Create a test verifying X is NOT available
- Example: "Landscape out of scope" → Test that NO Landscape option exists in UI

### 2. CREATE WORKFLOW/STATE TESTS
When AC mentions history, recent items, defaults, or settings:
- Create a WORKFLOW test: perform action → close → reopen → verify state persisted
- Example: "Recent Items shows last used presets" → Create doc with custom size → reopen dialog → verify Recent Items shows it

### 3. TEST MODAL BEHAVIOR
When AC mentions "modal dialog":
- Test that modal BLOCKS interaction with background
- Test focus is TRAPPED within modal (Tab cycles within modal)

### 4. TEST DUAL-ACTIONS
When AC describes two actions (e.g., "Create initializes; Close exits"):
- Create SEPARATE tests for each action
- Include a CANCEL test verifying no changes occur

### 5. TEST SETTING DEPENDENCIES
When AC says "follows setting" or "defaults to current setting":
- Create tests for EACH setting value (inches AND centimeters, etc.)
- Set the setting FIRST, then verify the dependent behavior

### 6. ADD EDGE CASE TESTS (Expert QA Thinking)
For EVERY feature, add tests that a senior QA would think of:
- **No selection state**: When AC says "enabled when selected" → test disabled state when nothing selected
- **Boundary values**: Test min/max limits, empty states, single vs multiple items
- **Error recovery**: What happens when an operation fails or is interrupted?
- **Undo/Redo**: If transformations are applied, can they be undone?
- **Cross-feature interaction**: Does this feature affect/conflict with related features?
Example edge cases for "Rotate" feature:
- Rotate with no object selected → verify command disabled
- Rotate multiple times → verify cumulative rotation
- Rotate then Undo → verify object returns to original orientation

### 7. WRITE SPECIFIC STEPS (Never Generic)
BAD: "Verify the feature works correctly"
GOOD: "Verify the Units dropdown shows 'cm'"

BAD: "Perform the action"
GOOD: "Click the 'Mirror Horizontally' button in the Tools menu"

### 8. VERIFY UI CONTROLS EXIST
When AC lists fields/controls:
- Create a test that verifies EACH control is displayed
- Example: "Fields: Width, Height, Units" → Verify Width field displayed, verify Height field displayed, etc.

## FORMATTING RULES

### Title Format
`{{story_id}}-{{id}}: {{Feature}} / {{Area}} / {{Scenario}}`

### TITLE QUALITY RULES (CRITICAL)
Every title MUST be:
1. **COMPLETE** - No truncated or incomplete phrases
2. **MEANINGFUL** - Clearly describes what the test verifies
3. **SPECIFIC** - Not generic or vague
4. **GRAMMATICALLY CORRECT** - Reads as a proper sentence fragment

**BAD TITLES (Never use):**
- "Display content without requiring" ❌ (incomplete - missing what?)
- "Feature availability" ❌ (too generic)
- "Selection behavior" ❌ (too vague - what behavior?)
- "Verify functionality" ❌ (meaningless)
- "Test the feature" ❌ (not descriptive)
- "User can access" ❌ (not a scenario)

**GOOD TITLES (Use these patterns):**
- "Display content without internet connection" ✓ (complete)
- "Default preset shows Letter 8×11 Portrait" ✓ (specific)
- "Selecting User Manual opens in-app viewer" ✓ (describes action & result)
- "Recent items populated after document creation" ✓ (describes workflow)
- "No external browser launched when viewing manual" ✓ (describes negative test)
- "Touch interaction on iPad and Android Tablet" ✓ (describes platform scope)

**Scenario Patterns:**
- For menu access: "[Command] menu access" or "[Command] appears in [Menu]"
- For behavior: "[Action] [result/outcome]"
- For settings: "[Setting] follows [configuration]"
- For negative: "No [excluded feature] option available"
- For state: "[State] persists after [action]"
- For accessibility: "[Accessibility method] on [Platform]"

### ID Sequence
- First test: AC1
- Subsequent: 005, 010, 015, 020...

### Step Structure
- Step 1: Always PRE-REQ (expected empty)
- Last step: Always Close/Exit (expected empty)
- Middle steps: Concrete actions with specific expected results

### Accessibility Tests (EXACT format)
`{{story_id}}-{{id}}: {{Feature}} / Accessibility / {{TestType}} ({{EXACT_PLATFORM}})`
- Area MUST be exactly "Accessibility"
- Platform in parentheses MUST match EXACTLY from platforms list
- Include platform-specific tools (Accessibility Insights for Windows, VoiceOver for iPad, etc.)'''

    def build_user_prompt(self, test_cases_json: str) -> str:
        """
        Build STRUCTURED user prompt with story-specific data.

        Sections:
        1. STORY METADATA
        2. SCOPE (in-scope + out-of-scope ACs)
        3. HARD REQUIREMENTS
        4. CONSTRAINTS
        5. STEP TEMPLATES
        6. SEED TEST CASES
        """
        # Build each section
        metadata_section = self._build_metadata_section()
        scope_section = self._build_scope_section()
        requirements_section = self._build_hard_requirements()
        constraints_section = self._build_constraints_section_compact()
        step_templates_section = self._build_step_templates_compact()
        seed_section = self._build_seed_section(test_cases_json)

        return f'''{metadata_section}

{scope_section}

{requirements_section}

{constraints_section}

{step_templates_section}

{seed_section}'''

    def _build_metadata_section(self) -> str:
        """Build story metadata section."""
        return f'''## STORY METADATA
- story_id: {self.ctx.story_id}
- feature: {self.ctx.feature_name}
- app: {self.ctx.app_name} ({self.ctx.app_type})
- platforms: {json.dumps(self.ctx.platforms)}
- feature_types: {json.dumps(self.ctx.feature_types)}'''

    def _build_scope_section(self) -> str:
        """Build scope section with in-scope and out-of-scope ACs."""
        lines = ["## SCOPE"]

        # In-scope ACs (numbered)
        lines.append("\n### In-Scope Acceptance Criteria (MUST cover)")
        for i, ac in enumerate(self.ctx.acceptance_criteria_in_scope, 1):
            lines.append(f"{i}. {ac}")

        # Out-of-scope ACs (explicitly excluded)
        if self.ctx.acceptance_criteria_out_of_scope:
            lines.append("\n### Out-of-Scope (DO NOT cover)")
            for ac in self.ctx.acceptance_criteria_out_of_scope:
                lines.append(f"- [EXCLUDED] {ac}")

        # QA Prep if available
        if self.ctx.qa_prep:
            lines.append(f"\n### QA Prep Context\n{self.ctx.qa_prep}")

        return "\n".join(lines)

    def _build_hard_requirements(self) -> str:
        """Build hard minimum requirements section based on story complexity."""
        # Calculate requirements dynamically
        reqs = calculate_test_requirements(
            ac_count=len(self.ctx.acceptance_criteria_in_scope),
            feature_types=self.ctx.feature_types,
            boundary_entities=self.ctx.boundary_entities,
            comprehensive_workflows=self.ctx.comprehensive_workflows,
            format_variations=self.ctx.format_variations,
            platform_count=len(self.ctx.platforms),
            qa_prep=self.ctx.qa_prep or ""
        )

        # Store for potential access by other methods
        self._test_requirements = reqs

        lines = [
            "## HARD REQUIREMENTS (MUST meet all)",
            "",
            f"### Minimum Test Counts (complexity score: {reqs.complexity_score:.1%})",
            f"- min_total: {reqs.min_total}",
            f"- max_total: {reqs.max_total}",
            f"- core_positive: >= {reqs.min_core} (one per AC, minimum 3)",
            f"- negative: >= {reqs.min_negative} (error/invalid state tests)",
            f"- edge_cases: >= {reqs.min_edge} (boundary/edge conditions)",
        ]

        if reqs.min_state > 0:
            lines.append(f"- state_undo: >= {reqs.min_state} (undo/redo/state tests)")

        lines.extend([
            f"- accessibility: EXACTLY {reqs.min_accessibility} (one per platform)",
            "",
            "### Accessibility Tests (EXACT format required)",
            f"required_platforms: {json.dumps(self.ctx.platforms)}",
            "Each accessibility test MUST:",
            "- Have Area = \"Accessibility\"",
            "- Have platform name in parentheses matching EXACTLY from list above",
            f"- Example: \"{self.ctx.story_id}-070: {self.ctx.feature_name} / Accessibility / Keyboard navigation ({self.ctx.platforms[0]})\"" if self.ctx.platforms else "",
            "",
            "### Boundary-Bearing Entities (edge/negative tests MUST relate to these)",
            f"boundary_entities: {json.dumps(self.ctx.boundary_entities)}",
        ])

        if self.ctx.edge_disallowed_areas:
            lines.extend([
                "",
                "### Edge-Disallowed Areas (NO boundary tests for these unless AC mentions them)",
                f"{json.dumps(self.ctx.edge_disallowed_areas)}",
            ])

        # Add format variation requirements
        if self.ctx.format_variations:
            lines.extend([
                "",
                "### Format Variation Coverage (MUST generate separate test per format)",
            ])
            for category, formats in self.ctx.format_variations.items():
                lines.append(f"- {category}: Create separate test for EACH format: {', '.join(formats)}")
            lines.append("Each format test must have identical workflow steps but with the specific format.")

        # Add comprehensive workflow requirements
        if self.ctx.comprehensive_workflows:
            lines.extend([
                "",
                "### Comprehensive Workflow Steps (MUST include ALL steps in each test)",
            ])
            for workflow_type, steps in self.ctx.comprehensive_workflows.items():
                lines.append(f"\n**{workflow_type.replace('_', ' ').title()}** tests MUST include:")
                for i, step in enumerate(steps, 1):
                    lines.append(f"  {i}. {step}")
            lines.append("\nDo NOT create minimal tests - each test must complete the FULL workflow.")

        return "\n".join(lines)

    def _build_constraints_section_compact(self) -> str:
        """Build compact constraints section."""
        lines = ["## CONSTRAINTS"]

        # Unavailable features
        if self.ctx.unavailable_features:
            lines.append("\n### Unsupported Features (never test)")
            lines.append(json.dumps(self.ctx.unavailable_features[:10]))

        # Forbidden terms
        if self.ctx.forbidden_words:
            lines.append("\n### Forbidden Terms (never use)")
            lines.append(json.dumps(self.ctx.forbidden_words[:10]))

        # Allowed areas
        if self.ctx.allowed_areas:
            lines.append("\n### Allowed Areas (for title)")
            lines.append(json.dumps(self.ctx.allowed_areas))

        return "\n".join(lines)

    def _build_step_templates_compact(self) -> str:
        """Build compact step templates section."""
        prereq = self.ctx.prereq_template.format(app_name=self.ctx.app_name)
        launch = self.ctx.launch_step.format(app_name=self.ctx.app_name)
        close = self.ctx.close_step.format(app_name=self.ctx.app_name)

        templates = {
            "prereq": {"action": prereq, "expected": ""},
            "launch": {"action": launch, "expected": self.ctx.launch_expected},
            "create_file": {"action": self.ctx.create_file_step, "expected": self.ctx.create_file_expected},
            "close": {"action": close, "expected": ""}
        }

        return f'''## STEP TEMPLATES
```json
{json.dumps(templates, indent=2)}
```

Structure: prereq → launch → create_file (if menu access needed) → feature steps → close'''

    def _build_derived_tests_section(self) -> str:
        """Build section with expert-derived test scenarios from AC analysis."""
        derived_scenarios = []

        # Analyze each AC for implicit test scenarios
        for idx, ac in enumerate(self.ctx.acceptance_criteria_in_scope):
            ac_lower = ac.lower()

            # 1. Detect "out of scope" → negative test
            if 'out' in ac_lower and 'scope' in ac_lower:
                match = re.search(r'(\w+(?:\s+\w+)?)\s+(?:is\s+)?(?:out|not)\s+(?:of\s+)?scope', ac_lower)
                if match:
                    excluded = match.group(1).strip()
                    derived_scenarios.append({
                        'type': 'negative',
                        'source_ac': idx + 1,
                        'title': f"No {excluded} option available (out of scope)",
                        'description': f"Verify {excluded} is NOT displayed in the UI"
                    })

            # 2. Detect "only X" → test opposite not available
            match = re.search(r'(?:orientation|mode|type)\s*=\s*(\w+)', ac_lower)
            if match:
                only_value = match.group(1)
                opposites = {'portrait': 'Landscape', 'landscape': 'Portrait'}
                if only_value in opposites:
                    derived_scenarios.append({
                        'type': 'negative',
                        'source_ac': idx + 1,
                        'title': f"No {opposites[only_value]} option available ({only_value.capitalize()} only)",
                        'description': f"Verify {opposites[only_value]} option is NOT displayed"
                    })

            # 3. Detect "recent items" → workflow test
            if 'recent' in ac_lower and ('items' in ac_lower or 'preset' in ac_lower):
                derived_scenarios.append({
                    'type': 'workflow',
                    'source_ac': idx + 1,
                    'title': "Recent items populated after document creation",
                    'description': "Create document with custom size → reopen dialog → verify Recent Items shows preset"
                })
                derived_scenarios.append({
                    'type': 'workflow',
                    'source_ac': idx + 1,
                    'title': "Recent items displays without errors when empty",
                    'description': "On fresh install, verify Recent Items section displays without crash"
                })

            # 4. Detect "modal" → focus trap and background blocking tests
            if 'modal' in ac_lower:
                derived_scenarios.append({
                    'type': 'negative',
                    'source_ac': idx + 1,
                    'title': "Modal blocks interaction with canvas behind",
                    'description': "With modal open, attempt to click canvas behind → verify no interaction"
                })

            # 5. Detect "follows setting" → setting sync tests
            if 'follow' in ac_lower and 'setting' in ac_lower:
                derived_scenarios.append({
                    'type': 'workflow',
                    'source_ac': idx + 1,
                    'title': "Units dropdown follows setting (inches)",
                    'description': "Set unit setting to inches → open dialog → verify dropdown shows 'in'"
                })
                derived_scenarios.append({
                    'type': 'workflow',
                    'source_ac': idx + 1,
                    'title': "Units dropdown follows setting (centimeters)",
                    'description': "Set unit setting to cm → open dialog → verify dropdown shows 'cm'"
                })

            # 6. Detect dual actions (Create/Close buttons)
            if ('create' in ac_lower or 'initialize' in ac_lower) and ('close' in ac_lower or 'exit' in ac_lower or 'cancel' in ac_lower):
                derived_scenarios.append({
                    'type': 'positive',
                    'source_ac': idx + 1,
                    'title': "Create button creates new canvas using selected settings",
                    'description': "Set custom size/units → click Create → verify new blank canvas with settings"
                })
                derived_scenarios.append({
                    'type': 'negative',
                    'source_ac': idx + 1,
                    'title': "Close button cancels without creating new canvas",
                    'description': "Modify values → click Close → verify NO new document created, user stays on current doc"
                })

            # 7. Detect default values
            match = re.search(r'default(?:\s+preset)?\s*=\s*["\']?([^"\'\.]+)', ac, re.IGNORECASE)
            if match:
                default_val = match.group(1).strip()
                derived_scenarios.append({
                    'type': 'positive',
                    'source_ac': idx + 1,
                    'title': f"Default preset shows {default_val}",
                    'description': f"Open dialog → verify preset details show '{default_val}'"
                })

            # 8. Detect fields/controls to verify
            if 'field' in ac_lower and (':' in ac or 'available' in ac_lower or 'include' in ac_lower):
                derived_scenarios.append({
                    'type': 'positive',
                    'source_ac': idx + 1,
                    'title': "Required sections and controls display",
                    'description': "Open dialog → verify ALL listed fields/sections are displayed"
                })

        if not derived_scenarios:
            return ""

        lines = ["## EXPERT QA DERIVED SCENARIOS", ""]
        lines.append("Based on AC analysis, you MUST include tests for these scenarios:")
        lines.append("")

        for i, scenario in enumerate(derived_scenarios[:15], 1):  # Limit to 15
            lines.append(f"{i}. **[{scenario['type'].upper()}]** {scenario['title']} (from AC{scenario['source_ac']})")
            lines.append(f"   → {scenario['description']}")
            lines.append("")

        return "\n".join(lines)

    def _build_seed_section(self, test_cases_json: str) -> str:
        """Build seed test cases section with expert-derived scenarios."""
        derived_section = self._build_derived_tests_section()

        try:
            data = json.loads(test_cases_json)
            test_cases = data.get('test_cases', data) if isinstance(data, dict) else data

            # Reduce seed tests
            reduced = reduce_seed_tests(test_cases)

            seed_json = f'''## SEED TEST CASES
Review, correct, and SIGNIFICANTLY enhance these tests:
```json
{json.dumps({"test_cases": reduced}, indent=2)}
```'''

            tasks = f'''
## YOUR TASK (Expert QA Level)

1. **TRANSFORM generic tests into SPECIFIC tests**
   - Replace "Verify the feature works" with actual verification like "Verify dropdown shows 'in'"
   - Replace "Perform the action" with specific action like "Click 'Mirror Horizontally' in Tools menu"

2. **ADD all derived scenarios above** (if not already covered)

3. **ADD EDGE CASE TESTS** based on your expert QA analysis:
   - Boundary conditions (min/max values, empty states, single item vs multiple)
   - Error handling (invalid inputs, unsupported operations, timeouts)
   - State transitions (before/after, enabled/disabled states)
   - Think: "What would a senior QA engineer test that isn't obvious from the AC?"

4. **ADD NEGATIVE TESTS for exclusions and constraints**:
   - "out of scope" → verify NOT available
   - "only X" → verify opposite NOT available
   - "enabled only when" → verify disabled state behavior

5. **ENSURE workflow tests** verify state persistence:
   - Recent items: create → reopen → verify
   - Settings sync: change setting → verify behavior follows

6. **GENERATE {len(self.ctx.platforms)} accessibility tests** with:
   - Platform-specific tools (Accessibility Insights, VoiceOver, Accessibility Scanner)
   - Exact platform names in titles: {', '.join(self.ctx.platforms)}

7. **FIX any forbidden language**: {', '.join(self.ctx.forbidden_words[:5])}'''

            if derived_section:
                return f"{derived_section}\n\n{seed_json}\n{tasks}"
            return f"{seed_json}\n{tasks}"

        except json.JSONDecodeError:
            return f'''## SEED TEST CASES
```json
{test_cases_json}
```'''

    @staticmethod
    def _format_list(items: List[str], prefix: str = "- ") -> str:
        """Format a list of items as bullet points."""
        if not items:
            return ""
        return "\n".join([f"{prefix}{item}" for item in items])


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def build_prompts_for_project(
    config,  # ProjectConfig
    story_id: str,
    feature_name: str,
    acceptance_criteria: List[str],
    qa_prep: str,
    test_cases_json: str
) -> tuple:
    """
    Convenience function to build both system and user prompts.

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    builder = PromptBuilder.from_project_config(
        config=config,
        story_id=story_id,
        feature_name=feature_name,
        acceptance_criteria=acceptance_criteria,
        qa_prep=qa_prep
    )

    return builder.build_system_prompt(), builder.build_user_prompt(test_cases_json)
