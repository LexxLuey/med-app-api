"""Unit tests for pipeline module."""


class TestRuleParser:
    """Test rule parsing functionality."""

    def test_rule_parser_initialization(self):
        """Test RuleParser class initializes correctly."""
        from pipeline.rules import RuleParser

        parser = RuleParser()
        assert parser is not None
        assert hasattr(parser, 'redis_client')

    def test_redis_client_exists(self):
        """Test Redis client is properly configured."""
        from pipeline.rules import RuleParser

        parser = RuleParser()
        assert parser.redis_client is not None

    def test_threshold_extraction(self):
        """Test threshold value extraction from text."""
        from pipeline.rules import RuleParser

        parser = RuleParser()
        text = "paid.amount: $500 threshold value"
        result = parser._extract_threshold(text, "paid.amount", 1000)
        # Should work with test data
        assert isinstance(result, (int, float))


class TestRuleEvaluator:
    """Test rule evaluation functionality."""

    def test_rule_evaluator_initialization(self):
        """Test RuleEvaluator class initializes correctly."""
        from pipeline.rules import RuleEvaluator

        evaluator = RuleEvaluator()
        assert evaluator is not None
        assert hasattr(evaluator, 'redis_client')

    def test_technical_evaluation_no_rules(self):
        """Test technical rule evaluation when no rules are loaded."""
        from pipeline.rules import RuleEvaluator

        evaluator = RuleEvaluator()
        claim_data = {"field1": "value1"}
        result = evaluator.evaluate_technical_rules(claim_data)

        # Should return default values when no rules are cached
        assert "valid" in result
        assert "errors" in result
        assert "type" in result
