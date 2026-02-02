"""Integration tests for embedding parser.

These tests require OPENAI_API_KEY to be set and will make real API calls.
Skip these tests in CI by using: pytest -m "not integration"
"""
import os
import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Skip entire module if OpenAI key not available
requires_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)


@requires_openai
class TestEmbeddingParserIntegration:
    """Integration tests for embedding-based AC parsing."""

    @pytest.fixture(autouse=True)
    def setup_embedding(self):
        """Enable embedding for tests."""
        os.environ["EMBEDDING_ENABLED"] = "true"
        yield
        os.environ["EMBEDDING_ENABLED"] = "false"

    def test_provider_available(self):
        """Provider should be available with API key."""
        from core.services.embeddings import create_embedding_provider

        provider = create_embedding_provider()
        assert provider is not None
        assert provider.is_available()

    def test_embed_single_text(self):
        """Should generate embedding for single text."""
        from core.services.embeddings import create_embedding_provider

        provider = create_embedding_provider()
        result = provider.embed("bring to front")

        assert result is not None
        assert result.dimensions == 1536  # text-embedding-3-small
        assert len(result.vector) == 1536

    def test_embed_batch(self):
        """Should generate embeddings for batch of texts."""
        from core.services.embeddings import create_embedding_provider

        provider = create_embedding_provider()
        texts = ["bring to front", "send to back", "enable feature"]
        results = provider.embed_batch(texts)

        assert len(results) == 3
        assert all(r.dimensions == 1536 for r in results)

    def test_pattern_index_loads(self):
        """Should load and embed all patterns."""
        from core.services.embeddings import (
            create_embedding_provider,
            EmbeddingCache,
            EmbeddingPatternIndex
        )

        provider = create_embedding_provider()
        cache = EmbeddingCache()
        index = EmbeddingPatternIndex(
            provider, cache, "patterns/ac_patterns.json"
        )

        index.load_patterns()

        assert index.is_loaded
        assert index.pattern_count > 0
        assert len(index.get_categories()) == 3  # action, outcome, boundary

    def test_semantic_matcher_finds_similar(self):
        """Should find similar patterns for input text."""
        from core.services.embeddings import (
            create_embedding_provider,
            EmbeddingCache,
            EmbeddingPatternIndex,
            SemanticMatcher
        )

        provider = create_embedding_provider()
        cache = EmbeddingCache()
        index = EmbeddingPatternIndex(
            provider, cache, "patterns/ac_patterns.json"
        )
        index.load_patterns()

        matcher = SemanticMatcher(provider, index, cache, threshold=0.75)

        # Test novel phrasing
        matches = matcher.find_similar(
            "move above other objects",
            category="action"
        )

        assert len(matches) > 0
        assert matches[0].pattern_text == "bring to front"
        assert matches[0].similarity_score >= 0.75

    def test_embedding_parser_parses_novel_phrasing(self):
        """Should parse novel phrasings correctly."""
        from core.services.nlp.embedding_parser import EmbeddingSemanticParser

        parser = EmbeddingSemanticParser(threshold=0.75)

        if not parser.is_available:
            pytest.skip("Embedding parser not available")

        result = parser.parse("User can move the shape above all other objects")

        assert result.method == "embedding"
        assert result.action_verb == "bring"
        assert result.confidence >= 0.75

    def test_hybrid_parser_uses_embedding(self):
        """Hybrid parser should use embedding layer when enabled."""
        from core.services.nlp.hybrid_parser import create_parser

        parser = create_parser(embedding_enabled=True, embedding_threshold=0.75)

        if not parser.embedding_available:
            pytest.skip("Embedding not available")

        result = parser.parse("move above other objects")

        assert parser.last_method == "embedding"
        assert result.action_verb == "bring"

    def test_hybrid_parser_fallback_on_low_confidence(self):
        """Should fall back to spaCy/regex when embedding confidence low."""
        from core.services.nlp.hybrid_parser import create_parser

        parser = create_parser(
            embedding_enabled=True,
            embedding_threshold=0.99  # Very high threshold
        )

        if not parser.embedding_available:
            pytest.skip("Embedding not available")

        # This should fall back because 0.99 threshold is very high
        result = parser.parse("completely unrelated text about weather")

        # Should use spaCy or regex fallback
        assert parser.last_method in ["spacy", "regex"]


@requires_openai
class TestEmbeddingAccuracy:
    """Accuracy benchmarks for embedding matching."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup embedding for tests."""
        os.environ["EMBEDDING_ENABLED"] = "true"
        yield
        os.environ["EMBEDDING_ENABLED"] = "false"

    def test_action_pattern_accuracy(self):
        """Test accuracy of action pattern matching."""
        from core.services.embeddings import (
            create_embedding_provider,
            EmbeddingCache,
            EmbeddingPatternIndex,
            SemanticMatcher
        )

        provider = create_embedding_provider()
        cache = EmbeddingCache()
        index = EmbeddingPatternIndex(
            provider, cache, "patterns/ac_patterns.json"
        )
        index.load_patterns()
        matcher = SemanticMatcher(provider, index, cache, threshold=0.75)

        test_cases = [
            # (input, expected_canonical)
            ("bring to front", "bring to front"),
            ("move above other objects", "bring to front"),
            ("send to back", "send to back"),
            ("enable the feature", "enable"),
            ("disable the option", "disable"),
            ("rotate the shape", "rotate"),
            ("turn on the setting", "enable"),
            ("turn off the setting", "disable"),
        ]

        correct = 0
        for input_text, expected in test_cases:
            match = matcher.match_action(input_text)
            if match and match.pattern_text == expected:
                correct += 1

        accuracy = correct / len(test_cases)
        print(f"\nAction pattern accuracy: {accuracy:.1%} ({correct}/{len(test_cases)})")

        # Should achieve at least 75% accuracy
        assert accuracy >= 0.75, f"Accuracy {accuracy:.1%} below threshold"
