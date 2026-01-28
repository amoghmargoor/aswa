# Task 3.2.1: Pydantic Extraction Models (Entity, Risk, Opportunity, Pattern)

## Context

You are working on the ASWA (AI-driven insight aggregation platform) project, a polyglot microservices system. The insight-engine service at `/services/insight-engine/` uses LLMs to extract structured insights from documents.

The LLM client abstraction is already implemented at:
- `/services/insight-engine/src/aswa_insight/llm/client.py` - Abstract LLMClient with `complete_structured()` method
- `/services/insight-engine/src/aswa_insight/llm/bedrock.py` - AWS Bedrock implementation
- `/services/insight-engine/src/aswa_insight/llm/azure.py` - Azure OpenAI implementation
- `/services/insight-engine/src/aswa_insight/llm/openai_client.py` - OpenAI implementation

The config is at `/services/insight-engine/src/aswa_insight/config.py`.

## Objective

Create comprehensive Pydantic models for structured extraction of insights from documents. These models will be used with the instructor library for LLM-powered extraction.

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/models/__init__.py`
Export all models from the submodules.

### 2. Create `/services/insight-engine/src/aswa_insight/models/base.py`
Base classes and common types:

```python
from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class ConfidenceLevel(str, Enum):
    """Confidence level categories."""
    VERY_LOW = "very_low"      # 0.0 - 0.2
    LOW = "low"                # 0.2 - 0.4
    MEDIUM = "medium"          # 0.4 - 0.6
    HIGH = "high"              # 0.6 - 0.8
    VERY_HIGH = "very_high"    # 0.8 - 1.0

class SourceReference(BaseModel):
    """Reference to source text."""
    text: str = Field(..., description="The exact quoted text from the source")
    page: int | None = Field(None, description="Page number if applicable")
    section: str | None = Field(None, description="Section name if applicable")
    start_offset: int | None = Field(None, description="Character offset in document")
    end_offset: int | None = Field(None, description="End character offset")

class ExtractedInsightBase(BaseModel):
    """Base class for all extracted insights."""
    model_config = ConfigDict(use_enum_values=True)

    confidence: Annotated[float, Field(ge=0.0, le=1.0, description="Confidence score 0-1")]
    sources: list[SourceReference] = Field(default_factory=list, description="Source references")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get categorical confidence level."""
        ...
```

### 3. Create `/services/insight-engine/src/aswa_insight/models/entities.py`
Entity extraction models:

```python
class EntityType(str, Enum):
    """Types of entities that can be extracted."""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    PRODUCT = "product"
    TECHNOLOGY = "technology"
    EVENT = "event"
    DATE = "date"
    MONEY = "money"
    PERCENTAGE = "percentage"
    REGULATION = "regulation"
    METRIC = "metric"
    OTHER = "other"

class EntityRelationshipType(str, Enum):
    """Types of relationships between entities."""
    WORKS_FOR = "works_for"
    OWNS = "owns"
    PARTNER_OF = "partner_of"
    COMPETITOR_OF = "competitor_of"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"
    MANAGES = "manages"
    RELATED_TO = "related_to"

class ExtractedEntity(ExtractedInsightBase):
    """An entity extracted from text."""
    name: str = Field(..., min_length=1, max_length=500, description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    description: str = Field(..., max_length=2000, description="Brief description")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    attributes: dict[str, str] = Field(default_factory=dict, description="Key attributes")

class EntityRelationship(BaseModel):
    """A relationship between two entities."""
    source_entity: str = Field(..., description="Name of source entity")
    target_entity: str = Field(..., description="Name of target entity")
    relationship_type: EntityRelationshipType
    description: str = Field(..., description="Description of relationship")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    bidirectional: bool = Field(False, description="If relationship goes both ways")

class EntityExtractionResult(BaseModel):
    """Result of entity extraction from a document."""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[EntityRelationship] = Field(default_factory=list)
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 4. Create `/services/insight-engine/src/aswa_insight/models/risks.py`
Risk extraction models:

```python
class RiskCategory(str, Enum):
    """Categories of business risks."""
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    STRATEGIC = "strategic"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    REPUTATIONAL = "reputational"
    MARKET = "market"
    TECHNOLOGY = "technology"
    LEGAL = "legal"
    ENVIRONMENTAL = "environmental"
    OTHER = "other"

class Severity(str, Enum):
    """Risk severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"

class Likelihood(str, Enum):
    """Risk likelihood levels."""
    ALMOST_CERTAIN = "almost_certain"
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    RARE = "rare"

class TimeHorizon(str, Enum):
    """Time horizon for risk materialization."""
    IMMEDIATE = "immediate"      # < 1 month
    SHORT_TERM = "short_term"    # 1-6 months
    MEDIUM_TERM = "medium_term"  # 6-18 months
    LONG_TERM = "long_term"      # > 18 months

class MitigationStrategy(BaseModel):
    """A suggested mitigation for a risk."""
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=2000)
    effort: Literal["low", "medium", "high"]
    effectiveness: Literal["low", "medium", "high"]

class ExtractedRisk(ExtractedInsightBase):
    """A risk identified in the document."""
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., max_length=3000)
    category: RiskCategory
    severity: Severity
    likelihood: Likelihood
    time_horizon: TimeHorizon | None = None
    impact_description: str = Field(..., max_length=1000, description="Potential impact")
    affected_areas: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    mitigations: list[MitigationStrategy] = Field(default_factory=list)
    risk_score: Annotated[float, Field(ge=0.0, le=100.0)] | None = None

class RiskExtractionResult(BaseModel):
    """Result of risk extraction from a document."""
    risks: list[ExtractedRisk] = Field(default_factory=list)
    overall_risk_level: Severity | None = None
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 5. Create `/services/insight-engine/src/aswa_insight/models/opportunities.py`
Opportunity extraction models:

```python
class OpportunityCategory(str, Enum):
    """Categories of business opportunities."""
    GROWTH = "growth"
    COST_REDUCTION = "cost_reduction"
    EFFICIENCY = "efficiency"
    INNOVATION = "innovation"
    MARKET_EXPANSION = "market_expansion"
    PARTNERSHIP = "partnership"
    ACQUISITION = "acquisition"
    PRODUCT = "product"
    TALENT = "talent"
    TECHNOLOGY = "technology"
    OTHER = "other"

class ImpactLevel(str, Enum):
    """Potential impact levels."""
    TRANSFORMATIONAL = "transformational"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class EffortLevel(str, Enum):
    """Required effort levels."""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class ActionItem(BaseModel):
    """A concrete action to pursue an opportunity."""
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    priority: Literal["high", "medium", "low"]
    estimated_effort: EffortLevel
    dependencies: list[str] = Field(default_factory=list)

class ExtractedOpportunity(ExtractedInsightBase):
    """An opportunity identified in the document."""
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., max_length=3000)
    category: OpportunityCategory
    impact: ImpactLevel
    effort: EffortLevel
    time_to_value: TimeHorizon | None = None
    potential_value: str | None = Field(None, description="Estimated value if quantifiable")
    prerequisites: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list, description="Associated risks")
    related_entities: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    strategic_alignment: str | None = Field(None, max_length=500)

class OpportunityExtractionResult(BaseModel):
    """Result of opportunity extraction from a document."""
    opportunities: list[ExtractedOpportunity] = Field(default_factory=list)
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 6. Create `/services/insight-engine/src/aswa_insight/models/patterns.py`
Pattern extraction models:

```python
class PatternType(str, Enum):
    """Types of patterns that can be identified."""
    TREND = "trend"
    CORRELATION = "correlation"
    ANOMALY = "anomaly"
    CYCLE = "cycle"
    THRESHOLD = "threshold"
    COMPARISON = "comparison"
    DISTRIBUTION = "distribution"
    SEQUENCE = "sequence"
    OTHER = "other"

class TrendDirection(str, Enum):
    """Direction of a trend."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"
    CYCLICAL = "cyclical"

class PatternFrequency(str, Enum):
    """Frequency of recurring patterns."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    IRREGULAR = "irregular"
    ONE_TIME = "one_time"

class DataPoint(BaseModel):
    """A data point in a pattern."""
    label: str
    value: float | str
    timestamp: datetime | None = None

class ExtractedPattern(ExtractedInsightBase):
    """A pattern identified in the document."""
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., max_length=3000)
    pattern_type: PatternType
    frequency: PatternFrequency | None = None
    trend_direction: TrendDirection | None = None
    magnitude: str | None = Field(None, description="Quantified magnitude if available")
    time_period: str | None = Field(None, description="Time period covered")
    data_points: list[DataPoint] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    statistical_significance: str | None = None

class PatternExtractionResult(BaseModel):
    """Result of pattern extraction from a document."""
    patterns: list[ExtractedPattern] = Field(default_factory=list)
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 7. Create `/services/insight-engine/src/aswa_insight/models/insights.py`
Unified insight model that combines all types:

```python
class InsightType(str, Enum):
    """Types of insights."""
    ENTITY = "entity"
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    PATTERN = "pattern"

class Insight(BaseModel):
    """Unified insight model for storage."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    document_id: UUID
    insight_type: InsightType
    title: str
    description: str
    confidence: float
    severity: Severity | None = None  # For risks
    impact: ImpactLevel | None = None  # For opportunities
    category: str | None = None
    raw_data: dict = Field(default_factory=dict, description="Original extracted data")
    sources: list[SourceReference] = Field(default_factory=list)
    related_entity_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user_validated: bool = False
    user_feedback: str | None = None

    @classmethod
    def from_entity(cls, entity: ExtractedEntity, tenant_id: UUID, document_id: UUID) -> "Insight":
        """Create insight from extracted entity."""
        ...

    @classmethod
    def from_risk(cls, risk: ExtractedRisk, tenant_id: UUID, document_id: UUID) -> "Insight":
        """Create insight from extracted risk."""
        ...

    @classmethod
    def from_opportunity(cls, opportunity: ExtractedOpportunity, tenant_id: UUID, document_id: UUID) -> "Insight":
        """Create insight from extracted opportunity."""
        ...

    @classmethod
    def from_pattern(cls, pattern: ExtractedPattern, tenant_id: UUID, document_id: UUID) -> "Insight":
        """Create insight from extracted pattern."""
        ...
```

## Test Requirements

Create `/services/insight-engine/tests/models/` with comprehensive tests:

### `/services/insight-engine/tests/models/__init__.py`

### `/services/insight-engine/tests/models/test_entities.py`
```python
class TestExtractedEntity:
    def test_valid_entity_creation(self):
        """Test creating valid entity."""

    def test_entity_confidence_bounds(self):
        """Test confidence must be 0-1."""

    def test_entity_type_validation(self):
        """Test entity type enum validation."""

    def test_entity_with_aliases(self):
        """Test entity with multiple aliases."""

    def test_entity_serialization(self):
        """Test JSON serialization."""

class TestEntityRelationship:
    def test_valid_relationship(self):
        """Test creating valid relationship."""

    def test_bidirectional_relationship(self):
        """Test bidirectional flag."""

class TestEntityExtractionResult:
    def test_empty_result(self):
        """Test empty extraction result."""

    def test_result_with_entities_and_relationships(self):
        """Test full result."""
```

### `/services/insight-engine/tests/models/test_risks.py`
```python
class TestExtractedRisk:
    def test_valid_risk_creation(self):
        """Test creating valid risk."""

    def test_risk_score_calculation(self):
        """Test risk score from severity/likelihood."""

    def test_risk_with_mitigations(self):
        """Test risk with mitigation strategies."""

    def test_all_severity_levels(self):
        """Test all severity enum values."""

    def test_all_likelihood_levels(self):
        """Test all likelihood enum values."""

class TestMitigationStrategy:
    def test_valid_mitigation(self):
        """Test creating valid mitigation."""
```

### `/services/insight-engine/tests/models/test_opportunities.py`
```python
class TestExtractedOpportunity:
    def test_valid_opportunity_creation(self):
        """Test creating valid opportunity."""

    def test_opportunity_with_actions(self):
        """Test opportunity with action items."""

    def test_all_impact_levels(self):
        """Test all impact enum values."""

class TestActionItem:
    def test_valid_action_item(self):
        """Test creating valid action item."""
```

### `/services/insight-engine/tests/models/test_patterns.py`
```python
class TestExtractedPattern:
    def test_valid_pattern_creation(self):
        """Test creating valid pattern."""

    def test_pattern_with_data_points(self):
        """Test pattern with data points."""

    def test_all_pattern_types(self):
        """Test all pattern type enum values."""

    def test_trend_direction(self):
        """Test trend direction values."""
```

### `/services/insight-engine/tests/models/test_insights.py`
```python
class TestInsight:
    def test_insight_from_entity(self):
        """Test creating insight from entity."""

    def test_insight_from_risk(self):
        """Test creating insight from risk."""

    def test_insight_from_opportunity(self):
        """Test creating insight from opportunity."""

    def test_insight_from_pattern(self):
        """Test creating insight from pattern."""

    def test_insight_serialization(self):
        """Test JSON serialization for storage."""
```

## Additional Notes

1. All models should use `Field()` with descriptions for instructor compatibility
2. Use `Annotated` types for complex validations
3. Ensure all enums have sensible defaults where appropriate
4. Add `model_config = ConfigDict(use_enum_values=True)` for JSON serialization
5. Consider adding validators for cross-field validation (e.g., risk_score based on severity/likelihood)
6. All string fields should have reasonable max_length constraints
7. Use `default_factory` for mutable defaults (lists, dicts)

## Verification

After implementation:
1. Run `cd /services/insight-engine && python -m pytest tests/models/ -v`
2. Verify all models can be imported: `python -c "from aswa_insight.models import *"`
3. Check instructor compatibility by creating sample extractions
