package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Tenant data transfer object.
 */
@Schema(description = "Tenant information")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record TenantDto(
        @Schema(description = "Tenant ID", example = "123e4567-e89b-12d3-a456-426614174000")
        UUID id,

        @Schema(description = "Tenant name", example = "ACME Corp")
        String name,

        @Schema(description = "Unique slug", example = "acme-corp")
        String slug,

        @Schema(description = "Tenant settings")
        Map<String, Object> settings,

        @Schema(description = "Account status", example = "active")
        String status,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt,

        @Schema(description = "Last updated timestamp", example = "2024-01-15T10:30:00Z")
        Instant updatedAt
) {
}
