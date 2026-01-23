package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.Map;

/**
 * Request to update an existing tenant.
 */
@Schema(description = "Update tenant request")
public record UpdateTenantRequest(
        @Schema(description = "Tenant name", example = "ACME Corp")
        @Size(min = 2, max = 255, message = "Name must be between 2 and 255 characters")
        String name,

        @Schema(description = "Tenant settings")
        Map<String, Object> settings,

        @Schema(description = "Account status", example = "active")
        @Pattern(regexp = "active|suspended|inactive", message = "Status must be 'active', 'suspended', or 'inactive'")
        String status
) {
}
