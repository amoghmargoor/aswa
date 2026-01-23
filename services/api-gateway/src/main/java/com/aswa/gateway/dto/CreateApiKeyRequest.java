package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Request to create API key.
 */
@Schema(description = "Create API key request")
public record CreateApiKeyRequest(
        @Schema(description = "Key name/description", example = "Integration key for CI/CD")
        @NotBlank(message = "Name is required")
        @Size(min = 2, max = 255, message = "Name must be between 2 and 255 characters")
        String name
) {
}
