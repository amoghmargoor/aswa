package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Feedback request for insights.
 */
@Schema(description = "Submit feedback on insight")
public record FeedbackRequest(
        @Schema(description = "Feedback type", example = "confirmed", allowableValues = {"confirmed", "rejected", "modified"})
        @NotBlank(message = "Feedback is required")
        String feedback,

        @Schema(description = "Optional comment", example = "This is accurate")
        @Size(max = 1000, message = "Comment must not exceed 1000 characters")
        String comment
) {
}
