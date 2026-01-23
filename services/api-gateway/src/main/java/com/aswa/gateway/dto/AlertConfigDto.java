package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Alert configuration data transfer object.
 */
@Schema(description = "Alert configuration")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AlertConfigDto(
        @Schema(description = "Alert ID", example = "550e8400-e29b-41d4-a716-446655440000")
        UUID id,

        @Schema(description = "Alert name", example = "High severity risks")
        String name,

        @Schema(description = "Alert type", example = "insight_threshold")
        String alertType,

        @Schema(description = "Alert conditions")
        Map<String, Object> conditions,

        @Schema(description = "Alert actions")
        Map<String, Object> actions,

        @Schema(description = "Is alert enabled", example = "true")
        boolean enabled,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt,

        @Schema(description = "Last updated timestamp", example = "2024-01-15T10:30:00Z")
        Instant updatedAt
) {
}
