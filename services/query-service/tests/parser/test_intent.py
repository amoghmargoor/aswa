import pytest
from aswa_query.parser.intent import IntentClassifier
from aswa_query.parser.models import QueryIntent


class TestIntentClassifier:
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def test_summary_intent(self, classifier):
        """Test summary intent detection."""
        queries = [
            "Give me a summary of the document",
            "Summarize the key points",
            "What are the main highlights?",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.SUMMARY

    def test_risk_intent(self, classifier):
        """Test risk intent detection."""
        queries = [
            "What are the main risks?",
            "Show me potential threats",
            "What could go wrong?",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.RISK

    def test_comparison_intent(self, classifier):
        """Test comparison intent detection."""
        queries = [
            "Compare company A and company B",
            "What's the difference between X and Y?",
            "How does this compare to last year?",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.COMPARISON

    def test_trend_intent(self, classifier):
        """Test trend intent detection."""
        queries = [
            "What are the trends over time?",
            "How has revenue changed?",
            "Show me the growth pattern",
        ]
        for query in queries:
            intent, confidence = classifier.classify(query)
            assert intent == QueryIntent.TREND

    def test_factual_default(self, classifier):
        """Test factual is default for unclear queries."""
        intent, confidence = classifier.classify("What is the price?")
        assert intent in [QueryIntent.FACTUAL, QueryIntent.ENTITY]

    def test_confidence_score(self, classifier):
        """Test confidence scores are reasonable."""
        intent, confidence = classifier.classify("Summarize the risks")
        assert 0 <= confidence <= 1
