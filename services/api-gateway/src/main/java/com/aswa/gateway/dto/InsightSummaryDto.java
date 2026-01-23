package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.Map;

/**
 * Insight summary statistics.
 */
@Schema(description = "Summary of insights by type and severity")
public record InsightSummaryDto(
        @Schema(description = "Total number of insights", example = "1500")
        long totalInsights,

        @Schema(description = "Count by insight type")
        Map<String, Long> byType,

        @Schema(description = "Count by severity")
        Map<String, Long> bySeverity,

        @Schema(description = "Count by status")
        Map<String, Long> byStatus
) {
}
