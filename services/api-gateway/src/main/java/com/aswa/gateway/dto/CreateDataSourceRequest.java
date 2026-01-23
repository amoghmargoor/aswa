package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.Map;

/**
 * Request to create a new data source.
 */
@Schema(description = "Create data source request")
public record CreateDataSourceRequest(
        @Schema(description = "Data source name", example = "Confluence")
        @NotBlank(message = "Name is required")
        @Size(min = 2, max = 255, message = "Name must be between 2 and 255 characters")
        String name,

        @Schema(description = "Source type", example = "confluence")
        @NotBlank(message = "Source type is required")
        String sourceType,

        @Schema(description = "Configuration (e.g., base URL, etc.)")
        Map<String, Object> config,

        @Schema(description = "Credentials (will be encrypted)")
        Map<String, Object> credentials
) {
}
