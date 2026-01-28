from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class ValidationSeverity(str, Enum):
    """Severity of validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A validation issue found."""

    field: str
    message: str
    severity: ValidationSeverity
    value: Any = None


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    cleaned_data: BaseModel | None = None

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)


class ExtractionValidator:
    """Validate extraction results."""

    def __init__(
        self,
        min_confidence: float = 0.0,
        max_insights_per_extraction: int = 100,
        require_sources: bool = False,
    ):
        self.min_confidence = min_confidence
        self.max_insights_per_extraction = max_insights_per_extraction
        self.require_sources = require_sources
        self._custom_validators: list[Callable[[BaseModel], list[ValidationIssue]]] = []

    def register_validator(
        self,
        validator: Callable[[BaseModel], list[ValidationIssue]],
    ) -> None:
        """Register a custom validator function."""
        self._custom_validators.append(validator)

    def validate(self, extraction: BaseModel) -> ValidationResult:
        """Validate an extraction result.

        Args:
            extraction: The extracted data to validate

        Returns:
            ValidationResult with issues and cleaned data
        """
        issues: list[ValidationIssue] = []

        # Get data as dict for validation
        data = extraction.model_dump()

        # Validate confidence scores
        issues.extend(self._validate_confidences(data))

        # Validate insight counts
        issues.extend(self._validate_counts(data))

        # Validate sources if required
        if self.require_sources:
            issues.extend(self._validate_sources(data))

        # Run custom validators
        for validator in self._custom_validators:
            try:
                issues.extend(validator(extraction))
            except Exception as e:
                logger.warning("Custom validator failed", error=str(e))

        # Check for duplicate insights
        issues.extend(self._check_duplicates(data))

        # Determine if valid (no errors)
        valid = all(i.severity != ValidationSeverity.ERROR for i in issues)

        # Create cleaned data if valid
        cleaned = None
        if valid:
            cleaned = self._clean_data(extraction, issues)

        return ValidationResult(
            valid=valid,
            issues=issues,
            cleaned_data=cleaned,
        )

    def _validate_confidences(self, data: dict) -> list[ValidationIssue]:
        """Validate confidence scores."""
        issues = []

        def check_confidence(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                if "confidence" in obj:
                    conf = obj["confidence"]
                    if conf < self.min_confidence:
                        issues.append(
                            ValidationIssue(
                                field=f"{path}.confidence",
                                message=f"Confidence {conf:.2f} below minimum {self.min_confidence:.2f}",
                                severity=ValidationSeverity.WARNING,
                                value=conf,
                            )
                        )
                    if not 0 <= conf <= 1:
                        issues.append(
                            ValidationIssue(
                                field=f"{path}.confidence",
                                message=f"Confidence {conf} out of range [0, 1]",
                                severity=ValidationSeverity.ERROR,
                                value=conf,
                            )
                        )
                for key, value in obj.items():
                    check_confidence(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_confidence(item, f"{path}[{i}]")

        check_confidence(data)
        return issues

    def _validate_counts(self, data: dict) -> list[ValidationIssue]:
        """Validate insight counts."""
        issues = []

        for field_name in ["entities", "risks", "opportunities", "patterns"]:
            if field_name in data and isinstance(data[field_name], list):
                count = len(data[field_name])
                if count > self.max_insights_per_extraction:
                    issues.append(
                        ValidationIssue(
                            field=field_name,
                            message=f"Too many {field_name}: {count} > {self.max_insights_per_extraction}",
                            severity=ValidationSeverity.WARNING,
                            value=count,
                        )
                    )

        return issues

    def _validate_sources(self, data: dict) -> list[ValidationIssue]:
        """Validate source references."""
        issues = []

        def check_sources(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                if "sources" in obj:
                    sources = obj["sources"]
                    if not sources or len(sources) == 0:
                        issues.append(
                            ValidationIssue(
                                field=f"{path}.sources",
                                message="Missing source references",
                                severity=ValidationSeverity.WARNING,
                            )
                        )
                for key, value in obj.items():
                    check_sources(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_sources(item, f"{path}[{i}]")

        check_sources(data)
        return issues

    def _check_duplicates(self, data: dict) -> list[ValidationIssue]:
        """Check for duplicate insights."""
        issues = []

        for field_name in ["entities", "risks", "opportunities", "patterns"]:
            if field_name in data and isinstance(data[field_name], list):
                items = data[field_name]
                seen_titles = set()

                for i, item in enumerate(items):
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("name", "")
                        if title in seen_titles:
                            issues.append(
                                ValidationIssue(
                                    field=f"{field_name}[{i}]",
                                    message=f"Duplicate {field_name[:-1]}: {title}",
                                    severity=ValidationSeverity.WARNING,
                                    value=title,
                                )
                            )
                        seen_titles.add(title)

        return issues

    def _clean_data(
        self,
        extraction: BaseModel,
        issues: list[ValidationIssue],
    ) -> BaseModel:
        """Clean extraction data based on validation issues."""
        data = extraction.model_dump()

        # Filter out low-confidence items if any
        for field_name in ["entities", "risks", "opportunities", "patterns"]:
            if field_name in data and isinstance(data[field_name], list):
                data[field_name] = [
                    item
                    for item in data[field_name]
                    if item.get("confidence", 1.0) >= self.min_confidence
                ]

        return extraction.model_validate(data)
