package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Insight data transfer object.
 */
@Schema(description = "AI-generated insight")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record InsightDto(
        @Schema(description = "Insight ID", example = "550e8400-e29b-41d4-a716-446655440000")
        UUID id,

        @Schema(description = "Insight type", example = "entity", allowableValues = {"entity", "risk", "opportunity", "pattern", "anomaly"})
        String insightType,

        @Schema(description = "Insight title", example = "Critical security vulnerability detected")
        String title,

        @Schema(description = "Detailed description")
        String description,

        @Schema(description = "Insight content (structured data)")
        Map<String, Object> content,

        @Schema(description = "Confidence score (0-1)", example = "0.95")
        double confidence,

        @Schema(description = "Severity level", example = "high")
        String severity,

        @Schema(description = "Category", example = "security")
        String category,

        @Schema(description = "Tags")
        List<String> tags,

        @Schema(description = "Source document IDs")
        List<UUID> sourceDocuments,

        @Schema(description = "Evidence snippets")
        List<String> evidenceSnippets,

        @Schema(description = "Status", example = "active")
        String status,

        @Schema(description = "User feedback", example = "confirmed")
        String userFeedback,

        @Schema(description = "User who provided feedback")
        UUID feedbackBy,

        @Schema(description = "Feedback comment")
        String feedbackComment,

        @Schema(description = "Feedback timestamp", example = "2024-01-15T10:30:00Z")
        Instant feedbackAt,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt
) {
}
