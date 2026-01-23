package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.Map;

/**
 * Request to create alert configuration.
 */
@Schema(description = "Create alert request")
public record CreateAlertRequest(
        @Schema(description = "Alert name", example = "High severity risks")
        @NotBlank(message = "Name is required")
        @Size(min = 2, max = 255, message = "Name must be between 2 and 255 characters")
        String name,

        @Schema(description = "Alert type", example = "insight_threshold")
        @NotBlank(message = "Alert type is required")
        String alertType,

        @Schema(description = "Alert conditions (criteria to trigger)")
        Map<String, Object> conditions,

        @Schema(description = "Alert actions (what to do when triggered)")
        Map<String, Object> actions,

        @Schema(description = "Enable alert", example = "true", defaultValue = "true")
        Boolean enabled
) {
    public CreateAlertRequest {
        if (enabled == null) {
            enabled = true;
        }
    }
}
