package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Insight filter request for querying insights.
 */
@Schema(description = "Insight filter criteria")
public record InsightFilterRequest(
        @Schema(description = "Insight type", example = "risk")
        String insightType,

        @Schema(description = "Severity level", example = "high")
        String severity,

        @Schema(description = "Category", example = "security")
        String category,

        @Schema(description = "Status", example = "active")
        String status
) {
}
