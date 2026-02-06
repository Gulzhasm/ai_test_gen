"""Tests for the dynamic prompt builder."""
import json
import pytest
from core.services.llm.prompt_builder import (
    PromptBuilder,
    PromptContext,
    build_prompts_for_project,
    detect_feature_type,
    detect_feature_types,
    FEATURE_TYPE_PATTERNS,
    clean_acceptance_criteria,
    split_scope,
    safe_truncate,
    lint_seed_test,
    reduce_seed_tests,
    extract_boundary_entities,
    derive_edge_allowed_areas,
)


# =============================================================================
# ACCEPTANCE CHECKS (from requirements)
# =============================================================================

class TestAcceptanceChecks:
    """Acceptance checks from the refactoring requirements."""

    @pytest.fixture
    def sample_context(self):
        """Create a sample context for testing."""
        return PromptContext(
            app_name="Test App",
            app_type="desktop",
            story_id="12345",
            feature_name="Mirror Tool",
            acceptance_criteria=[
                "Acceptance Criteria:",
                "User can flip objects horizontally",
                "User can flip objects vertically",
                "[Out of Scope] User can flip multiple objects at once"
            ],
            qa_prep="Test the mirror functionality with various object types.",
            unavailable_features=["multi-select"],
            feature_notes={"mirror": "Only works on single objects"},
            ui_surfaces=["File Menu", "Canvas", "Tools Menu"],
            entry_points={"mirror": "Tools Menu"},
            platforms=["Windows 11", "iPad", "Android Tablet"],
            prereq_template="Pre-req: {app_name} is installed",
            launch_step="Launch {app_name}",
            launch_expected="App launches successfully",
            create_file_step="Create a new file.",
            create_file_expected="New file is created.",
            close_step="Close {app_name}",
            forbidden_words=["or", "if available"],
            allowed_areas=["File Menu", "Canvas", "Tools Menu"]
        )

    def test_system_prompt_length_reduced(self, sample_context):
        """CHECK 1: System prompt length reduced drastically."""
        builder = PromptBuilder(sample_context)
        system_prompt = builder.build_system_prompt()

        # Should be under 4KB (includes expert QA guidance)
        assert len(system_prompt) < 4000, f"System prompt too long: {len(system_prompt)} chars"

        # Should NOT contain repeated persona blocks
        assert system_prompt.count("SENIOR QA ENGINEER") == 1  # Exactly once
        assert system_prompt.count("10+ years") == 0  # No generic expert persona
        assert system_prompt.count("YOUR EXPERTISE") == 0

    def test_user_prompt_no_duplicated_rules(self, sample_context):
        """CHECK 2: User prompt does not include duplicated rule sections."""
        builder = PromptBuilder(sample_context)
        system_prompt = builder.build_system_prompt()
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        # Rule sections should be in system prompt only
        assert "## OUTPUT CONTRACT" in system_prompt
        assert "## OUTPUT CONTRACT" not in user_prompt

        assert "## EXPERT QA RULES" in system_prompt
        assert "## EXPERT QA RULES" not in user_prompt

        # No duplicated persona/expert blocks in user prompt
        assert "SENIOR QA ENGINEER" not in user_prompt
        assert "YOUR EXPERTISE" not in user_prompt

    def test_out_of_scope_acs_excluded(self, sample_context):
        """CHECK 3: Out-of-scope ACs appear ONLY under out_of_scope."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        # Out-of-scope AC should be in out-of-scope section
        assert "Out-of-Scope" in user_prompt or "out_of_scope" in user_prompt
        assert "[EXCLUDED]" in user_prompt

        # The out-of-scope AC should not be in in-scope section
        in_scope_acs = builder.ctx.acceptance_criteria_in_scope
        for ac in in_scope_acs:
            assert "flip multiple objects" not in ac.lower()

        # Verify preprocessing separated correctly
        assert len(builder.ctx.acceptance_criteria_out_of_scope) == 1
        assert "multiple objects" in builder.ctx.acceptance_criteria_out_of_scope[0].lower()

    def test_no_conflicting_constraints(self, sample_context):
        """CHECK 4: No hard conflicting constraints."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        # Should NOT have hard per-component counts
        assert "3-5 tests per component" not in user_prompt
        assert "3–5 tests per component" not in user_prompt

        # Should use hard minimums with clear counts
        assert "HARD REQUIREMENTS" in user_prompt
        assert "min_total" in user_prompt
        assert ">=" in user_prompt  # Uses >= for minimums

    def test_feature_types_multi_label(self, sample_context):
        """CHECK 5: Feature types are multi-label."""
        builder = PromptBuilder(sample_context)

        # Feature types should be a list
        assert isinstance(builder.ctx.feature_types, list)
        assert len(builder.ctx.feature_types) >= 1

        # User prompt should show list
        user_prompt = builder.build_user_prompt('{"test_cases": []}')
        assert "feature_types" in user_prompt
        assert "[" in user_prompt  # JSON array

    def test_qa_prep_truncation_no_mid_word(self):
        """CHECK 6: QA prep truncation never ends mid-word."""
        # Test with long text
        long_text = "This is a sentence. " * 200  # Way over 2000 chars

        result = safe_truncate(long_text, 100)

        # Should end with truncation marker
        assert result.endswith("…[truncated]")

        # Should not end mid-word (last char before marker should be space or punctuation)
        text_before_marker = result.replace("…[truncated]", "")
        last_char = text_before_marker[-1] if text_before_marker else ""
        assert not last_char.isalnum(), f"Truncated mid-word: '{result[-50:]}'"

    def test_seed_tests_minimal_fields(self):
        """CHECK 7: Seed tests JSON included is minimal fields only."""
        test_case = {
            'id': 'TC-001',
            'title': 'Test Title',
            'objective': 'Verify something',
            'extra_field': 'should be removed',
            'another_field': 'also removed',
            'steps': [
                {
                    'step': 1,
                    'action': 'Do something',
                    'expected': 'Something happens',
                    'notes': 'extra field'
                }
            ]
        }

        result = lint_seed_test(test_case)

        # Should only have required fields
        assert 'id' in result
        assert 'title' in result
        assert 'objective' in result
        assert 'steps' in result

        # Extra fields should be removed
        assert 'extra_field' not in result
        assert 'another_field' not in result

        # Steps should only have action and expected
        assert 'notes' not in result['steps'][0]
        assert 'step' not in result['steps'][0]


# =============================================================================
# FEATURE TYPE DETECTION TESTS
# =============================================================================

class TestFeatureTypeDetection:
    """Tests for feature type detection."""

    def test_detect_input_feature(self):
        """Test detection of input features."""
        feature_type = detect_feature_type("User Input Form", ["User can enter text in the field"])
        assert feature_type == "input"

    def test_detect_navigation_feature(self):
        """Test detection of navigation features."""
        feature_type = detect_feature_type("Help Menu", ["User can access help from the menu"])
        assert feature_type == "navigation"

    def test_detect_display_feature(self):
        """Test detection of display features."""
        feature_type = detect_feature_type("Version Info", ["Display the version number and show build info"])
        assert feature_type in ["display", "navigation"]

    def test_detect_object_manipulation_feature(self):
        """Test detection of object manipulation features."""
        feature_type = detect_feature_type("Mirror Tool", ["User can rotate selected objects"])
        assert feature_type == "object_manipulation"

    def test_default_feature_type(self):
        """Test default feature type when no patterns match."""
        feature_type = detect_feature_type("Unknown Feature", ["Does something generic"])
        assert feature_type == "general"

    def test_multi_label_detection(self):
        """Test multi-label feature detection."""
        # Feature with both input and object manipulation keywords
        types = detect_feature_types(
            "Coordinate Input Tool",
            [
                "User can enter coordinates",
                "User can move objects to coordinates",
                "User can rotate the object"
            ]
        )

        # Should return multiple types
        assert isinstance(types, list)
        # Should include relevant types (order may vary by score)
        assert 'input' in types or 'object_manipulation' in types

    def test_multi_label_returns_general_when_no_matches(self):
        """Test multi-label returns general when no patterns match."""
        types = detect_feature_types("Unknown", ["something generic"])
        assert types == ['general']


# =============================================================================
# PREPROCESSING HELPERS TESTS
# =============================================================================

class TestCleanAcceptanceCriteria:
    """Tests for AC cleaning."""

    def test_removes_header_bullets(self):
        """Test removal of header bullets."""
        raw_acs = [
            "Acceptance Criteria:",
            "User can save files",
            "AC:",
            "User can load files"
        ]
        cleaned = clean_acceptance_criteria(raw_acs)

        assert len(cleaned) == 2
        assert "User can save files" in cleaned
        assert "User can load files" in cleaned

    def test_removes_empty_bullets(self):
        """Test removal of empty bullets."""
        raw_acs = ["", "User can save", "  ", "User can load"]
        cleaned = clean_acceptance_criteria(raw_acs)

        assert len(cleaned) == 2

    def test_removes_leading_bullets(self):
        """Test removal of leading bullet characters."""
        raw_acs = [
            "- User can save",
            "* User can load",
            "• User can delete",
            "1. User can create"
        ]
        cleaned = clean_acceptance_criteria(raw_acs)

        assert all(not ac.startswith(('-', '*', '•', '1.')) for ac in cleaned)
        assert "User can save" in cleaned

    def test_deduplicates(self):
        """Test deduplication."""
        raw_acs = [
            "User can save files",
            "User can save files",
            "User can load files"
        ]
        cleaned = clean_acceptance_criteria(raw_acs)

        assert len(cleaned) == 2


class TestSplitScope:
    """Tests for scope splitting."""

    def test_splits_out_of_scope(self):
        """Test splitting out-of-scope ACs."""
        acs = [
            "User can save files",
            "[Out of Scope] User can export to PDF",
            "User can load files",
            "Excluded: User can print"
        ]
        in_scope, out_of_scope = split_scope(acs)

        assert len(in_scope) == 2
        assert len(out_of_scope) == 2
        assert "User can save files" in in_scope
        assert any("export" in ac.lower() for ac in out_of_scope)

    def test_handles_no_out_of_scope(self):
        """Test when there are no out-of-scope ACs."""
        acs = ["User can save", "User can load"]
        in_scope, out_of_scope = split_scope(acs)

        assert len(in_scope) == 2
        assert len(out_of_scope) == 0


class TestSafeTruncate:
    """Tests for safe truncation."""

    def test_no_truncation_needed(self):
        """Test when text is under limit."""
        text = "Short text"
        result = safe_truncate(text, 100)
        assert result == text

    def test_truncates_at_sentence(self):
        """Test truncation at sentence boundary."""
        text = "First sentence. Second sentence. Third sentence."
        result = safe_truncate(text, 35)

        assert "…[truncated]" in result
        assert result.endswith("…[truncated]")

    def test_truncates_at_word_boundary(self):
        """Test truncation at word boundary when no sentence end found."""
        text = "Word " * 50
        result = safe_truncate(text, 50)

        # Should end with truncation marker
        assert result.endswith("…[truncated]")

        # The text part should be complete words (no partial words)
        text_part = result.replace("…[truncated]", "").strip()
        # Each word in text_part should be "Word" (complete)
        words = text_part.split()
        assert all(w == "Word" for w in words), f"Found partial word in: {text_part}"

    def test_handles_empty_text(self):
        """Test handling of empty text."""
        result = safe_truncate("", 100)
        assert result == ""

        result = safe_truncate(None, 100)
        assert result is None


class TestSeedTestLinting:
    """Tests for seed test linting."""

    def test_removes_placeholders(self):
        """Test removal of placeholder text."""
        test_case = {
            'id': 'TC-001',
            'title': 'Verify functionality of feature',
            'objective': 'Verify that e.g. something works',
            'steps': [
                {'action': 'Click button if available', 'expected': 'Button responds'}
            ]
        }

        result = lint_seed_test(test_case)

        assert 'verify functionality' not in result['title'].lower()
        assert 'e.g.' not in result['objective']
        assert 'if available' not in result['steps'][0]['action']

    def test_reduces_to_minimal_fields(self):
        """Test reduction to minimal fields."""
        test_cases = [
            {'id': '1', 'title': 'T1', 'objective': 'O1', 'steps': [], 'extra': 'x'},
            {'id': '2', 'title': 'T2', 'objective': 'O2', 'steps': [], 'extra': 'x'},
        ]

        reduced = reduce_seed_tests(test_cases, max_size=10000)

        for tc in reduced:
            assert 'extra' not in tc

    def test_strips_html_tags(self):
        """Test that HTML tags are stripped from seed tests."""
        test_case = {
            'id': '1',
            'title': 'Test <b>Bold</b> Title',
            'objective': 'Verify that <b>Feature</b> works correctly',
            'steps': [
                {'action': 'Click <i>button</i>', 'expected': 'Dialog <strong>opens</strong>'}
            ]
        }

        result = lint_seed_test(test_case)

        assert '<b>' not in result['title']
        assert '<b>' not in result['objective']
        assert '<i>' not in result['steps'][0]['action']
        assert '<strong>' not in result['steps'][0]['expected']
        assert 'Bold' in result['title']
        assert 'Feature' in result['objective']


class TestContradictoryUnsupportedFiltering:
    """Tests for filtering contradictory unsupported features."""

    def test_filters_contradictory_features(self):
        """Test that features mentioned in ACs are filtered out."""
        from core.services.llm.prompt_builder import filter_contradictory_unsupported

        unsupported = ["multi-select", "cloud sync", "batch operations"]
        acs = ["Multi-selected objects transform together", "User can save files"]

        filtered = filter_contradictory_unsupported(unsupported, acs)

        # "multi-select" should be filtered (mentioned in AC)
        assert "multi-select" not in filtered
        # "cloud sync" should remain (not mentioned)
        assert "cloud sync" in filtered

    def test_keeps_unmentioned_features(self):
        """Test that unmentioned features are kept."""
        from core.services.llm.prompt_builder import filter_contradictory_unsupported

        unsupported = ["feature-a", "feature-b", "feature-c"]
        acs = ["User can do something else entirely"]

        filtered = filter_contradictory_unsupported(unsupported, acs)

        # All should remain since none are mentioned
        assert len(filtered) == 3


# =============================================================================
# ENTITY EXTRACTION AND EDGE-ALLOWED AREAS TESTS
# =============================================================================

class TestBoundaryEntityExtraction:
    """Tests for boundary-bearing entity extraction."""

    def test_extracts_file_entities(self):
        """Test extraction of file-related entities."""
        acs = ["User can open a file", "User can import documents"]
        entities = extract_boundary_entities(acs)

        assert 'file_input' in entities

    def test_extracts_transform_entities(self):
        """Test extraction of transform-related entities."""
        acs = ["User can rotate objects", "User can flip the selection"]
        entities = extract_boundary_entities(acs)

        assert 'object_transform' in entities

    def test_extracts_text_entities(self):
        """Test extraction of text input entities."""
        acs = ["User can type in the field", "User can enter coordinates"]
        entities = extract_boundary_entities(acs)

        assert 'text_input' in entities

    def test_extracts_state_entities(self):
        """Test extraction of state change entities."""
        acs = ["User can undo the action", "User can redo changes"]
        entities = extract_boundary_entities(acs)

        assert 'state_change' in entities

    def test_returns_default_when_no_match(self):
        """Test default entity when no patterns match."""
        acs = ["Something generic happens"]
        entities = extract_boundary_entities(acs)

        assert entities == ['in_scope_workflow']

    def test_extracts_multiple_entities(self):
        """Test extraction of multiple entity types."""
        acs = [
            "User can open a file",
            "User can rotate the object",
            "User can undo the action"
        ]
        entities = extract_boundary_entities(acs)

        assert len(entities) >= 2
        assert 'file_input' in entities
        assert 'object_transform' in entities


class TestEdgeAllowedAreas:
    """Tests for edge-allowed/disallowed area derivation."""

    def test_disallows_help_menu_by_default(self):
        """Test that Help Menu is disallowed for edge tests by default."""
        allowed_areas = ["File Menu", "Help Menu", "Canvas"]
        acs = ["User can save files"]

        edge_allowed, edge_disallowed = derive_edge_allowed_areas(allowed_areas, acs)

        assert "Help Menu" in edge_disallowed
        assert "Canvas" in edge_allowed
        assert "File Menu" in edge_allowed

    def test_allows_help_menu_when_referenced(self):
        """Test that Help Menu is allowed when referenced in ACs."""
        allowed_areas = ["File Menu", "Help Menu", "Canvas"]
        acs = ["User can access help documentation", "Help button is visible"]

        edge_allowed, edge_disallowed = derive_edge_allowed_areas(allowed_areas, acs)

        # Help is referenced, so it should be allowed
        assert "Help Menu" in edge_allowed or "Help Menu" not in edge_disallowed

    def test_allows_core_interaction_areas(self):
        """Test that core interaction areas are always allowed."""
        allowed_areas = ["Canvas", "Dialog Window", "Modal Window"]
        acs = ["Something unrelated"]

        edge_allowed, edge_disallowed = derive_edge_allowed_areas(allowed_areas, acs)

        assert "Canvas" in edge_allowed
        assert "Dialog Window" in edge_allowed


class TestFormatVariationDetection:
    """Tests for format variation detection."""

    def test_detects_image_formats(self):
        """Test that image format variations are detected."""
        from core.services.llm.prompt_builder import detect_format_variations

        acs = ["User can insert PNG image", "User can insert JPG image"]
        variations = detect_format_variations(acs)

        assert 'image' in variations
        assert 'PNG' in variations['image']
        assert 'JPG' in variations['image']
        assert 'BMP' in variations['image']

    def test_detects_document_formats(self):
        """Test that document format variations are detected when multiple formats mentioned."""
        from core.services.llm.prompt_builder import detect_format_variations

        # Requires 2+ explicit formats or "multiple formats" phrase
        acs = ["User can import PDF and DOCX documents"]
        variations = detect_format_variations(acs)

        assert 'document' in variations
        assert 'PDF' in variations['document']

    def test_no_document_variations_for_single_format(self):
        """Test that single format mention does NOT trigger variations."""
        from core.services.llm.prompt_builder import detect_format_variations

        # Single format should NOT trigger variations
        acs = ["User can import PDF document"]
        variations = detect_format_variations(acs)

        assert 'document' not in variations

    def test_no_variations_when_not_applicable(self):
        """Test that no variations are detected for non-file ACs."""
        from core.services.llm.prompt_builder import detect_format_variations

        acs = ["User can access help menu", "User can view about screen"]
        variations = detect_format_variations(acs)

        assert len(variations) == 0


class TestComprehensiveWorkflows:
    """Tests for comprehensive workflow extraction."""

    def test_extracts_image_file_workflow(self):
        """Test that image file workflow is extracted."""
        from core.services.llm.prompt_builder import extract_comprehensive_workflows

        entities = ['file_input', 'object_transform']
        acs = ["User can insert image", "User can move image"]
        workflows = extract_comprehensive_workflows(entities, acs)

        assert 'image_file' in workflows
        assert len(workflows['image_file']) >= 5  # At least 5 steps

    def test_extracts_text_field_workflow(self):
        """Test that text field workflow is extracted."""
        from core.services.llm.prompt_builder import extract_comprehensive_workflows

        entities = ['text_input']
        acs = ["User can add editable text field"]
        workflows = extract_comprehensive_workflows(entities, acs)

        assert 'text_field' in workflows
        assert len(workflows['text_field']) >= 4

    def test_extracts_overlay_visibility_workflow(self):
        """Test that overlay visibility workflow is extracted."""
        from core.services.llm.prompt_builder import extract_comprehensive_workflows

        entities = ['overlay_visibility']
        acs = ["North indicator is visible on top layer"]
        workflows = extract_comprehensive_workflows(entities, acs)

        assert 'overlay_indicator' in workflows
        assert len(workflows['overlay_indicator']) >= 3

    def test_no_workflow_for_navigation(self):
        """Test that no complex workflow for simple navigation."""
        from core.services.llm.prompt_builder import extract_comprehensive_workflows

        entities = ['selection']
        acs = ["User can select menu item"]
        workflows = extract_comprehensive_workflows(entities, acs)

        # Selection alone doesn't trigger comprehensive workflows
        assert 'image_file' not in workflows
        assert 'text_field' not in workflows


class TestComprehensivePromptGeneration:
    """Tests for comprehensive prompt generation with workflows."""

    @pytest.fixture
    def insert_image_context(self):
        """Create a context for insert image feature."""
        return PromptContext(
            app_name="QuickDraw",
            app_type="desktop",
            story_id="271917",
            feature_name="Insert Images",
            acceptance_criteria=[
                "User can insert PNG image",
                "User can insert JPG image",
                "User can insert BMP image",
                "Inserted images can be moved",
                "Inserted images can be resized",
                "Inserted images can be rotated",
                "Inserted images can be locked as background"
            ],
            qa_prep="Test image insertion",
            unavailable_features=[],
            feature_notes={},
            ui_surfaces=["Insert Menu", "Canvas"],
            entry_points={},
            platforms=["Windows 11", "iPad", "Android Tablet"],
            prereq_template="Pre-req: {app_name} is installed",
            launch_step="Launch {app_name}",
            launch_expected="App launches",
            create_file_step="Create a new file.",
            create_file_expected="New file is created.",
            close_step="Close {app_name}",
            forbidden_words=[],
            allowed_areas=["Insert Menu", "Canvas"]
        )

    def test_format_variations_in_prompt(self, insert_image_context):
        """Test that format variations appear in user prompt."""
        builder = PromptBuilder(insert_image_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        assert "Format Variation Coverage" in user_prompt
        assert "PNG" in user_prompt
        assert "JPG" in user_prompt
        assert "BMP" in user_prompt

    def test_comprehensive_workflow_in_prompt(self, insert_image_context):
        """Test that comprehensive workflow steps appear in user prompt."""
        builder = PromptBuilder(insert_image_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        assert "Comprehensive Workflow Steps" in user_prompt
        assert "FULL workflow" in user_prompt or "ALL steps" in user_prompt

    def test_system_prompt_has_comprehensive_rules(self, insert_image_context):
        """Test that system prompt has expert QA rules."""
        builder = PromptBuilder(insert_image_context)
        system_prompt = builder.build_system_prompt()

        # New expert QA rules
        assert "DERIVE NEGATIVE TESTS" in system_prompt
        assert "CREATE WORKFLOW/STATE TESTS" in system_prompt
        assert "WRITE SPECIFIC STEPS" in system_prompt


class TestHardRequirements:
    """Tests for hard minimum requirements."""

    @pytest.fixture
    def sample_context(self):
        """Create a sample context for testing."""
        return PromptContext(
            app_name="Test App",
            app_type="desktop",
            story_id="12345",
            feature_name="Mirror Tool",
            acceptance_criteria=[
                "User can flip objects horizontally",
                "User can flip objects vertically",
                "User can rotate objects"
            ],
            qa_prep="Test the mirror functionality",
            unavailable_features=["multi-select"],
            feature_notes={},
            ui_surfaces=["File Menu", "Canvas", "Tools Menu"],
            entry_points={},
            platforms=["Windows 11", "iPad", "Android Tablet"],
            prereq_template="Pre-req: {app_name} is installed",
            launch_step="Launch {app_name}",
            launch_expected="App launches",
            create_file_step="Create a new file.",
            create_file_expected="New file is created.",
            close_step="Close {app_name}",
            forbidden_words=["or"],
            allowed_areas=["File Menu", "Canvas", "Tools Menu", "Help Menu"]
        )

    def test_hard_requirements_in_user_prompt(self, sample_context):
        """Test that hard requirements appear in user prompt."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        # Should have hard requirements section
        assert "HARD REQUIREMENTS" in user_prompt
        assert "min_total" in user_prompt
        assert "max_total" in user_prompt
        assert "core_positive" in user_prompt
        assert "negative" in user_prompt
        assert "accessibility" in user_prompt

    def test_boundary_entities_in_user_prompt(self, sample_context):
        """Test that boundary entities appear in user prompt."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        assert "boundary_entities" in user_prompt

    def test_accessibility_exact_format(self, sample_context):
        """Test that accessibility format requirements are explicit."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        # Should have exact platform requirements
        assert "EXACTLY 3" in user_prompt or "EXACTLY" in user_prompt
        assert "Windows 11" in user_prompt
        assert "iPad" in user_prompt
        assert "Android Tablet" in user_prompt
        assert "required_platforms" in user_prompt

    def test_expert_qa_rules_in_system_prompt(self, sample_context):
        """Test that expert QA rules are in system prompt."""
        builder = PromptBuilder(sample_context)
        system_prompt = builder.build_system_prompt()

        # Check for expert QA mindset sections
        assert "DERIVE NEGATIVE TESTS FROM EXCLUSIONS" in system_prompt
        assert "TEST MODAL BEHAVIOR" in system_prompt


# =============================================================================
# PROMPT CONTEXT TESTS
# =============================================================================

class TestPromptContext:
    """Tests for PromptContext dataclass."""

    def test_context_creation(self):
        """Test creating a prompt context."""
        ctx = PromptContext(
            app_name="Test App",
            app_type="desktop",
            story_id="12345",
            feature_name="Test Feature",
            acceptance_criteria=["User can save file"],
            qa_prep="QA notes here",
            unavailable_features=["offline mode"],
            feature_notes={},
            ui_surfaces=["File Menu", "Canvas"],
            entry_points={"save": "File Menu"},
            platforms=["Windows 11", "iPad"],
            prereq_template="Pre-req: {app_name} is installed",
            launch_step="Launch {app_name}",
            launch_expected="App launches",
            create_file_step="Create a new file.",
            create_file_expected="New file is created.",
            close_step="Close {app_name}",
            forbidden_words=["or", "if available"],
            allowed_areas=["File Menu", "Canvas"]
        )

        assert ctx.story_id == "12345"
        assert ctx.feature_name == "Test Feature"
        assert ctx.app_name == "Test App"
        assert len(ctx.platforms) == 2

    def test_feature_type_property(self):
        """Test feature_type property backward compatibility."""
        ctx = PromptContext(
            app_name="Test App",
            app_type="desktop",
            story_id="12345",
            feature_name="Help Menu",
            acceptance_criteria=["User can access help from the menu"],
            qa_prep="",
            unavailable_features=[],
            feature_notes={},
            ui_surfaces=[],
            entry_points={},
            platforms=[],
            prereq_template="",
            launch_step="",
            launch_expected="",
            create_file_step="",
            create_file_expected="",
            close_step="",
            forbidden_words=[],
            allowed_areas=[]
        )

        # Should work without feature_types being set
        assert ctx.feature_type in ['navigation', 'general', 'display']


# =============================================================================
# PROMPT BUILDER TESTS
# =============================================================================

class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    @pytest.fixture
    def sample_context(self):
        """Create a sample context for testing."""
        return PromptContext(
            app_name="Test App",
            app_type="desktop",
            story_id="12345",
            feature_name="Mirror Tool",
            acceptance_criteria=[
                "User can flip objects horizontally",
                "User can flip objects vertically"
            ],
            qa_prep="Test the mirror functionality",
            unavailable_features=["multi-select"],
            feature_notes={"mirror": "Only works on single objects"},
            ui_surfaces=["File Menu", "Canvas", "Tools Menu"],
            entry_points={"mirror": "Tools Menu"},
            platforms=["Windows 11", "iPad"],
            prereq_template="Pre-req: {app_name} is installed",
            launch_step="Launch {app_name}",
            launch_expected="App launches successfully",
            create_file_step="Create a new file.",
            create_file_expected="New file is created.",
            close_step="Close {app_name}",
            forbidden_words=["or", "if available"],
            allowed_areas=["File Menu", "Canvas", "Tools Menu"]
        )

    def test_builder_initialization(self, sample_context):
        """Test builder initialization and preprocessing."""
        builder = PromptBuilder(sample_context)

        # Should preprocess ACs
        assert len(builder.ctx.acceptance_criteria_in_scope) == 2
        assert len(builder.ctx.feature_types) >= 1

    def test_build_system_prompt_structure(self, sample_context):
        """Test system prompt has correct structure."""
        builder = PromptBuilder(sample_context)
        system_prompt = builder.build_system_prompt()

        # Should have key sections
        assert "## OUTPUT CONTRACT" in system_prompt
        assert "## EXPERT QA RULES" in system_prompt
        assert "## FORMATTING RULES" in system_prompt

        # Should NOT have story-specific content
        assert sample_context.story_id not in system_prompt
        assert "Mirror Tool" not in system_prompt

    def test_build_user_prompt_structure(self, sample_context):
        """Test user prompt has correct sections."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        # Should have all required sections
        assert "## STORY METADATA" in user_prompt
        assert "## SCOPE" in user_prompt
        assert "## HARD REQUIREMENTS" in user_prompt
        assert "## CONSTRAINTS" in user_prompt
        assert "## STEP TEMPLATES" in user_prompt
        assert "## SEED TEST CASES" in user_prompt

        # Should have story-specific content
        assert sample_context.story_id in user_prompt
        assert sample_context.feature_name in user_prompt

    def test_platform_accessibility_in_user_prompt(self, sample_context):
        """Test platform-specific content in user prompt."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        assert "Windows 11" in user_prompt
        assert "iPad" in user_prompt

    def test_unavailable_features_in_constraints(self, sample_context):
        """Test unavailable features appear in constraints."""
        builder = PromptBuilder(sample_context)
        user_prompt = builder.build_user_prompt('{"test_cases": []}')

        assert "multi-select" in user_prompt


# =============================================================================
# BUILD PROMPTS FOR PROJECT TESTS
# =============================================================================

class TestBuildPromptsForProject:
    """Tests for the build_prompts_for_project helper function."""

    def test_build_prompts_with_minimal_config(self):
        """Test building prompts with minimal configuration."""

        class MockApplication:
            name = "Test App"
            app_type = "web"
            main_ui_surfaces = ["Dashboard"]
            entry_point_mappings = {}
            supported_platforms = ["Chrome"]
            prereq_template = "Pre-req: User logged in"
            launch_step = "Open app"
            launch_expected = "App opens"
            close_step = "Log out"
            unavailable_features = []
            feature_notes = {}

        class MockRules:
            forbidden_words = ["or"]
            allowed_areas = ["Dashboard"]

        class MockConfig:
            application = MockApplication()
            rules = MockRules()
            llm_model = "gpt-4"

        system_prompt, user_prompt = build_prompts_for_project(
            config=MockConfig(),
            story_id="99999",
            feature_name="Test Feature",
            acceptance_criteria=["AC1: User can do something"],
            qa_prep="Test notes",
            test_cases_json='[]'
        )

        assert "Test App" in user_prompt
        assert "99999" in user_prompt
        # System prompt should be reasonably sized (includes expert QA rules)
        assert len(system_prompt) < 4000


# =============================================================================
# FEATURE TYPE PATTERNS TESTS
# =============================================================================

class TestFeatureTypePatterns:
    """Tests for feature type pattern matching."""

    def test_input_patterns_exist(self):
        """Test input patterns are defined."""
        assert 'input' in FEATURE_TYPE_PATTERNS
        assert len(FEATURE_TYPE_PATTERNS['input']) > 0

    def test_navigation_patterns_exist(self):
        """Test navigation patterns are defined."""
        assert 'navigation' in FEATURE_TYPE_PATTERNS
        assert len(FEATURE_TYPE_PATTERNS['navigation']) > 0

    def test_display_patterns_exist(self):
        """Test display patterns are defined."""
        assert 'display' in FEATURE_TYPE_PATTERNS
        assert len(FEATURE_TYPE_PATTERNS['display']) > 0

    def test_object_manipulation_patterns_exist(self):
        """Test object manipulation patterns are defined."""
        assert 'object_manipulation' in FEATURE_TYPE_PATTERNS
        assert len(FEATURE_TYPE_PATTERNS['object_manipulation']) > 0


# =============================================================================
# COMPLEXITY-BASED TEST REQUIREMENTS TESTS
# =============================================================================

class TestCalculateTestRequirements:
    """Tests for simplified test count calculation.

    New logic:
    - min_total = AC count + accessibility (platform count) ONLY
    - Edge/negative/state are RECOMMENDED but NOT counted in minimum
    - This prevents artificial inflation of test counts
    """

    def test_import_works(self):
        """Test that calculate_test_requirements can be imported."""
        from core.services.llm.prompt_builder import calculate_test_requirements, TestRequirements
        assert callable(calculate_test_requirements)

    def test_returns_test_requirements_dataclass(self):
        """Test that function returns TestRequirements dataclass."""
        from core.services.llm.prompt_builder import calculate_test_requirements, TestRequirements

        reqs = calculate_test_requirements(
            ac_count=5,
            feature_types=['navigation'],
            boundary_entities=['selection'],
            comprehensive_workflows={},
            format_variations={},
            platform_count=3
        )

        assert isinstance(reqs, TestRequirements)
        assert hasattr(reqs, 'min_total')
        assert hasattr(reqs, 'max_total')
        assert hasattr(reqs, 'min_core')
        assert hasattr(reqs, 'min_negative')
        assert hasattr(reqs, 'min_edge')
        assert hasattr(reqs, 'min_state')
        assert hasattr(reqs, 'min_accessibility')
        assert hasattr(reqs, 'complexity_score')
        assert hasattr(reqs, 'complexity_factors')

    def test_ac_count_equals_min_core(self):
        """Test that AC count directly equals min_core tests."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs_3_acs = calculate_test_requirements(
            ac_count=3,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        reqs_10_acs = calculate_test_requirements(
            ac_count=10,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        # min_core should equal ac_count exactly
        assert reqs_3_acs.min_core == 3
        assert reqs_10_acs.min_core == 10

    def test_min_core_matches_ac_count_even_for_single_ac(self):
        """Test that min_core matches AC count even for 1 AC."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=1,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        # min_core should equal ac_count, no artificial minimum
        assert reqs.min_core == 1

    def test_high_complexity_types_add_edge_negative(self):
        """Test that high complexity types (input, object_manipulation) add edge/negative tests."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs_navigation = calculate_test_requirements(
            ac_count=5,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        reqs_object_manip = calculate_test_requirements(
            ac_count=5,
            feature_types=['object_manipulation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        # Navigation (simple) should have no edge/negative
        assert reqs_navigation.min_negative == 0
        assert reqs_navigation.min_edge == 0

        # Object manipulation (complex) should have edge/negative
        assert reqs_object_manip.min_negative >= 1
        assert reqs_object_manip.min_edge >= 1

    def test_simple_feature_only_core_and_accessibility(self):
        """Test simple features only require core + accessibility tests."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=5,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=3
        )

        # Simple feature: min = core + accessibility only
        assert reqs.min_core == 5
        assert reqs.min_accessibility == 3
        assert reqs.min_negative == 0
        assert reqs.min_edge == 0
        assert reqs.min_state == 0
        assert reqs.min_total == 8  # 5 + 3

    def test_platform_count_affects_accessibility(self):
        """Test that platform count directly affects accessibility test count."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs_1_platform = calculate_test_requirements(
            ac_count=5,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        reqs_3_platforms = calculate_test_requirements(
            ac_count=5,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=3
        )

        assert reqs_1_platform.min_accessibility == 1
        assert reqs_3_platforms.min_accessibility == 3

    def test_state_change_entity_adds_state_tests_for_complex(self):
        """Test that state_change entity adds state/undo tests for complex features."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs_no_state = calculate_test_requirements(
            ac_count=5,
            feature_types=['object_manipulation'],
            boundary_entities=['selection'],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        reqs_with_state = calculate_test_requirements(
            ac_count=5,
            feature_types=['object_manipulation'],
            boundary_entities=['state_change'],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        # State tests only added when state_change entity present
        assert reqs_with_state.min_state == 1
        assert reqs_no_state.min_state == 0

    def test_min_total_is_core_plus_accessibility_only(self):
        """Test that min_total equals core + accessibility (edge/negative not counted)."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=5,
            feature_types=['object_manipulation'],
            boundary_entities=['state_change'],
            comprehensive_workflows={},
            format_variations={},
            platform_count=3
        )

        # min_total = core + accessibility ONLY
        expected_total = reqs.min_core + reqs.min_accessibility

        assert reqs.min_total == expected_total
        # Edge/negative/state are recommendations, not added to min_total
        assert reqs.min_negative == 1  # Recommended
        assert reqs.min_edge == 1      # Recommended
        assert reqs.min_state == 1     # Recommended (because state_change entity)

    def test_max_total_greater_than_min_total(self):
        """Test that max_total is always greater than min_total."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=5,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        assert reqs.max_total > reqs.min_total

    def test_complexity_score_capped_at_1(self):
        """Test that complexity score never exceeds 1.0."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=20,
            feature_types=['input', 'object_manipulation', 'calculation'],
            boundary_entities=['file_input', 'object_transform', 'text_input', 'state_change'],
            comprehensive_workflows={},
            format_variations={'image': ['PNG', 'JPG', 'BMP']},
            platform_count=5,
            qa_prep=""
        )

        assert reqs.complexity_score <= 1.0

    def test_complexity_factors_tracked(self):
        """Test that complexity factors are tracked in the result."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=5,
            feature_types=['input'],
            boundary_entities=['text_input'],
            comprehensive_workflows={},
            format_variations={},
            platform_count=2
        )

        assert 'ac_count' in reqs.complexity_factors
        assert reqs.complexity_factors['ac_count'] == 5
        assert 'feature_type' in reqs.complexity_factors
        assert 'is_complex' in reqs.complexity_factors
        assert 'breakdown' in reqs.complexity_factors

    def test_simple_navigation_story(self):
        """Test a simple navigation story gets minimal requirements."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=3,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={},
            platform_count=1
        )

        # Simple: core (3) + accessibility (1) = 4
        assert reqs.min_total == 4
        assert reqs.min_negative == 0
        assert reqs.min_edge == 0

    def test_complex_object_manipulation_story(self):
        """Test a complex object manipulation story gets appropriate requirements."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs = calculate_test_requirements(
            ac_count=11,
            feature_types=['object_manipulation'],
            boundary_entities=['object_transform', 'state_change'],
            comprehensive_workflows={},
            format_variations={},
            platform_count=3
        )

        # min_total = core (11) + accessibility (3) = 14 (edge/neg/state are recommendations)
        assert reqs.min_core == 11
        assert reqs.min_accessibility == 3
        assert reqs.min_total == 14  # Just core + accessibility
        # Edge/negative/state are recommended but NOT counted in min_total
        assert reqs.min_negative == 1  # Recommended
        assert reqs.min_edge == 1      # Recommended
        assert reqs.min_state == 1     # Recommended (state_change entity)

    def test_format_variations_tracked_in_factors(self):
        """Test that format variations are tracked in complexity factors."""
        from core.services.llm.prompt_builder import calculate_test_requirements

        reqs_with_formats = calculate_test_requirements(
            ac_count=5,
            feature_types=['navigation'],
            boundary_entities=[],
            comprehensive_workflows={},
            format_variations={'image': ['PNG', 'JPG', 'BMP']},
            platform_count=1
        )

        # Format variations are tracked for prompt guidance
        assert 'format_variations' in reqs_with_formats.complexity_factors
        assert reqs_with_formats.complexity_factors['format_variations'] == 3
