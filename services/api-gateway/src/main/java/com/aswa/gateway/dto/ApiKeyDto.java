package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.UUID;

/**
 * API key data transfer object.
 */
@Schema(description = "API key")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ApiKeyDto(
        @Schema(description = "API key ID", example = "550e8400-e29b-41d4-a716-446655440000")
        UUID id,

        @Schema(description = "Key name/description", example = "Integration key for CI/CD")
        String name,

        @Schema(description = "API key (only shown once on creation)", example = "ak_live_abc123...")
        String key,

        @Schema(description = "Key prefix (visible identifier)", example = "ak_live_abc")
        String keyPrefix,

        @Schema(description = "Is key active", example = "true")
        boolean active,

        @Schema(description = "Last used timestamp", example = "2024-01-15T10:30:00Z")
        Instant lastUsedAt,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt
) {
}
