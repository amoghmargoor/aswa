import pytest

from aswa_insight.extraction.validators import (
    ExtractionValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from aswa_insight.models.entities import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
)


class TestExtractionValidator:
    @pytest.fixture
    def validator(self):
        return ExtractionValidator(min_confidence=0.5)

    def test_validate_valid_extraction(self, validator):
        """Test validation of valid extraction."""
        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test description",
                    confidence=0.8,
                )
            ]
        )

        result = validator.validate(extraction)
        assert result.valid is True

    def test_validate_low_confidence(self, validator):
        """Test validation flags low confidence."""
        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.3,  # Below threshold
                )
            ]
        )

        result = validator.validate(extraction)
        assert any(i.severity == ValidationSeverity.WARNING for i in result.issues)
        assert any("below minimum" in i.message for i in result.issues)

    def test_validate_empty_extraction(self, validator):
        """Test validation of empty extraction."""
        extraction = EntityExtractionResult(entities=[])

        result = validator.validate(extraction)
        assert result.valid is True
        assert result.cleaned_data is not None

    def test_validate_too_many_insights(self):
        """Test validation warns on too many insights."""
        validator = ExtractionValidator(max_insights_per_extraction=5)

        entities = [
            ExtractedEntity(
                name=f"Entity {i}",
                entity_type=EntityType.OTHER,
                description="Test",
                confidence=0.8,
            )
            for i in range(10)
        ]
        extraction = EntityExtractionResult(entities=entities)

        result = validator.validate(extraction)
        assert any("Too many" in i.message for i in result.issues)
        assert any(i.field == "entities" for i in result.issues)

    def test_validate_duplicates(self, validator):
        """Test validation detects duplicates."""
        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Same Name",
                    entity_type=EntityType.ORGANIZATION,
                    description="First",
                    confidence=0.8,
                ),
                ExtractedEntity(
                    name="Same Name",
                    entity_type=EntityType.ORGANIZATION,
                    description="Second",
                    confidence=0.7,
                ),
            ]
        )

        result = validator.validate(extraction)
        assert any("Duplicate" in i.message for i in result.issues)

    def test_validate_sources_not_required_by_default(self):
        """Test that sources are not required by default."""
        validator = ExtractionValidator(require_sources=False)

        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.8,
                    sources=[],  # Empty sources
                )
            ]
        )

        result = validator.validate(extraction)
        # Should not have warning about missing sources
        assert not any("source" in i.message.lower() for i in result.issues)

    def test_validate_sources_required(self):
        """Test validation warns when sources are required but missing."""
        validator = ExtractionValidator(require_sources=True)

        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.8,
                    sources=[],
                )
            ]
        )

        result = validator.validate(extraction)
        assert any("source" in i.message.lower() for i in result.issues)

    def test_custom_validator(self, validator):
        """Test custom validator registration."""

        def custom_check(extraction):
            return [
                ValidationIssue(
                    field="custom",
                    message="Custom check",
                    severity=ValidationSeverity.INFO,
                )
            ]

        validator.register_validator(custom_check)
        extraction = EntityExtractionResult(entities=[])

        result = validator.validate(extraction)
        assert any(i.field == "custom" for i in result.issues)
        assert any(i.message == "Custom check" for i in result.issues)

    def test_custom_validator_exception_handling(self, validator):
        """Test that failing custom validators don't break validation."""

        def failing_validator(extraction):
            raise ValueError("Validator error")

        validator.register_validator(failing_validator)
        extraction = EntityExtractionResult(entities=[])

        # Should not raise, just log warning
        result = validator.validate(extraction)
        assert result.valid is True

    def test_cleaned_data_filters_low_confidence(self):
        """Test that cleaned data filters out low confidence items."""
        validator = ExtractionValidator(min_confidence=0.5)

        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="High Confidence",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.8,
                ),
                ExtractedEntity(
                    name="Low Confidence",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.3,
                ),
            ]
        )

        result = validator.validate(extraction)
        assert result.valid is True
        assert result.cleaned_data is not None
        # Only high confidence item should remain in cleaned data
        assert len(result.cleaned_data.entities) == 1
        assert result.cleaned_data.entities[0].name == "High Confidence"

    def test_multiple_custom_validators(self, validator):
        """Test multiple custom validators."""

        def check1(extraction):
            return [
                ValidationIssue(
                    field="check1", message="Check 1", severity=ValidationSeverity.INFO
                )
            ]

        def check2(extraction):
            return [
                ValidationIssue(
                    field="check2", message="Check 2", severity=ValidationSeverity.INFO
                )
            ]

        validator.register_validator(check1)
        validator.register_validator(check2)

        extraction = EntityExtractionResult(entities=[])
        result = validator.validate(extraction)

        assert any(i.field == "check1" for i in result.issues)
        assert any(i.field == "check2" for i in result.issues)


class TestValidationResult:
    def test_error_count(self):
        """Test error count calculation."""
        result = ValidationResult(
            valid=False,
            issues=[
                ValidationIssue("f1", "msg1", ValidationSeverity.ERROR),
                ValidationIssue("f2", "msg2", ValidationSeverity.WARNING),
                ValidationIssue("f3", "msg3", ValidationSeverity.ERROR),
            ],
        )
        assert result.error_count == 2
        assert result.warning_count == 1

    def test_empty_issues(self):
        """Test with no issues."""
        result = ValidationResult(valid=True, issues=[])
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_all_warnings(self):
        """Test with only warnings."""
        result = ValidationResult(
            valid=True,
            issues=[
                ValidationIssue("f1", "msg1", ValidationSeverity.WARNING),
                ValidationIssue("f2", "msg2", ValidationSeverity.WARNING),
            ],
        )
        assert result.error_count == 0
        assert result.warning_count == 2

    def test_info_not_counted_as_warning(self):
        """Test that INFO severity is not counted as warning."""
        result = ValidationResult(
            valid=True,
            issues=[
                ValidationIssue("f1", "msg1", ValidationSeverity.INFO),
                ValidationIssue("f2", "msg2", ValidationSeverity.WARNING),
            ],
        )
        assert result.warning_count == 1


class TestValidationIssue:
    def test_creation(self):
        """Test ValidationIssue creation."""
        issue = ValidationIssue(
            field="test_field",
            message="Test message",
            severity=ValidationSeverity.ERROR,
            value="test_value",
        )
        assert issue.field == "test_field"
        assert issue.message == "Test message"
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.value == "test_value"

    def test_default_value(self):
        """Test ValidationIssue default value."""
        issue = ValidationIssue(
            field="test_field",
            message="Test message",
            severity=ValidationSeverity.WARNING,
        )
        assert issue.value is None
