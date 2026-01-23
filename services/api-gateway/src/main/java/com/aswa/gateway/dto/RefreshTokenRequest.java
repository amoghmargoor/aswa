package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/**
 * Refresh token request.
 */
@Schema(description = "Refresh token request")
public record RefreshTokenRequest(
        @Schema(description = "Refresh token", example = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        @NotBlank(message = "Refresh token is required")
        String refreshToken
) {
}
