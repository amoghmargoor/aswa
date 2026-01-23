package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.UUID;

/**
 * User data transfer object.
 */
@Schema(description = "User information")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record UserDto(
        @Schema(description = "User ID", example = "550e8400-e29b-41d4-a716-446655440000")
        UUID id,

        @Schema(description = "Tenant ID", example = "123e4567-e89b-12d3-a456-426614174000")
        UUID tenantId,

        @Schema(description = "Email address", example = "user@example.com")
        String email,

        @Schema(description = "Full name", example = "John Doe")
        String fullName,

        @Schema(description = "User role", example = "admin", allowableValues = {"super_admin", "admin", "user"})
        String role,

        @Schema(description = "Account status", example = "active", allowableValues = {"active", "suspended", "inactive"})
        String status,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt,

        @Schema(description = "Last updated timestamp", example = "2024-01-15T10:30:00Z")
        Instant updatedAt
) {
}
