package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.Map;

/**
 * Request to create a new tenant.
 */
@Schema(description = "Create tenant request")
public record CreateTenantRequest(
        @Schema(description = "Tenant name", example = "ACME Corp")
        @NotBlank(message = "Name is required")
        @Size(min = 2, max = 255, message = "Name must be between 2 and 255 characters")
        String name,

        @Schema(description = "Unique slug (lowercase, alphanumeric, hyphens)", example = "acme-corp")
        @NotBlank(message = "Slug is required")
        @Pattern(regexp = "^[a-z0-9-]+$", message = "Slug must be lowercase alphanumeric with hyphens")
        @Size(min = 2, max = 100, message = "Slug must be between 2 and 100 characters")
        String slug,

        @Schema(description = "Tenant settings (optional)")
        Map<String, Object> settings
) {
}
