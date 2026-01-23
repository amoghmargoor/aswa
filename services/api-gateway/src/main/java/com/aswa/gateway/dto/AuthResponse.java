package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Authentication response with tokens and user info.
 */
@Schema(description = "Authentication response")
public record AuthResponse(
        @Schema(description = "Access token (JWT)", example = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        String accessToken,

        @Schema(description = "Refresh token", example = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        String refreshToken,

        @Schema(description = "Token type", example = "Bearer")
        String tokenType,

        @Schema(description = "Token expiration in seconds", example = "3600")
        long expiresIn,

        @Schema(description = "User information")
        UserDto user
) {
    public static AuthResponse of(String accessToken, String refreshToken, long expiresIn, UserDto user) {
        return new AuthResponse(accessToken, refreshToken, "Bearer", expiresIn, user);
    }
}
