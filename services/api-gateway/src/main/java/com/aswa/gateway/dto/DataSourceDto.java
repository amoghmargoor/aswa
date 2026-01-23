package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Data source data transfer object.
 */
@Schema(description = "Data source configuration")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record DataSourceDto(
        @Schema(description = "Data source ID", example = "550e8400-e29b-41d4-a716-446655440000")
        UUID id,

        @Schema(description = "Data source name", example = "Confluence")
        String name,

        @Schema(description = "Source type", example = "confluence")
        String sourceType,

        @Schema(description = "Configuration (non-sensitive)")
        Map<String, Object> config,

        @Schema(description = "Status", example = "active")
        String status,

        @Schema(description = "Last sync timestamp", example = "2024-01-15T10:30:00Z")
        Instant lastSyncAt,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt,

        @Schema(description = "Last updated timestamp", example = "2024-01-15T10:30:00Z")
        Instant updatedAt
) {
}
