package com.aswa.gateway.security;

import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for JwtService.
 */
class JwtServiceTest {

    private JwtService jwtService;
    private static final String SECRET = "test-secret-key-must-be-at-least-32-characters-long-for-hs256";

    @BeforeEach
    void setUp() {
        jwtService = new JwtService(SECRET, 3600, 604800);
    }

    @Test
    void generateToken_ShouldCreateValidToken() {
        // Given
        UUID userId = UUID.randomUUID();
        UUID tenantId = UUID.randomUUID();
        String email = "test@example.com";
        String roles = "admin,user";

        // When
        String token = jwtService.generateToken(userId, tenantId, email, roles);

        // Then
        assertThat(token).isNotNull();
        assertThat(token).isNotEmpty();
    }

    @Test
    void validateToken_ShouldReturnClaims_WhenTokenIsValid() {
        // Given
        UUID userId = UUID.randomUUID();
        UUID tenantId = UUID.randomUUID();
        String email = "test@example.com";
        String roles = "admin";
        String token = jwtService.generateToken(userId, tenantId, email, roles);

        // When
        Claims claims = jwtService.validateToken(token).block();

        // Then
        assertThat(claims).isNotNull();
        assertThat(claims.getSubject()).isEqualTo(userId.toString());
        assertThat(claims.get("tenant_id", String.class)).isEqualTo(tenantId.toString());
        assertThat(claims.get("email", String.class)).isEqualTo(email);
        assertThat(claims.get("roles", String.class)).isEqualTo(roles);
    }

    @Test
    void validateToken_ShouldFail_WhenTokenIsInvalid() {
        // Given
        String invalidToken = "invalid.token.here";

        // When / Then
        assertThatThrownBy(() -> jwtService.validateToken(invalidToken).block())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Invalid JWT token");
    }

    @Test
    void generateRefreshToken_ShouldCreateValidToken() {
        // Given
        UUID userId = UUID.randomUUID();
        UUID tenantId = UUID.randomUUID();

        // When
        String refreshToken = jwtService.generateRefreshToken(userId, tenantId);

        // Then
        assertThat(refreshToken).isNotNull();
        assertThat(refreshToken).isNotEmpty();

        Claims claims = jwtService.validateToken(refreshToken).block();
        assertThat(claims.getSubject()).isEqualTo(userId.toString());
        assertThat(claims.get("type", String.class)).isEqualTo("refresh");
    }

    @Test
    void extractUserId_ShouldReturnCorrectUserId() {
        // Given
        UUID userId = UUID.randomUUID();
        UUID tenantId = UUID.randomUUID();
        String token = jwtService.generateToken(userId, tenantId, "test@example.com", "user");

        // When
        UUID extractedUserId = jwtService.extractUserId(token);

        // Then
        assertThat(extractedUserId).isEqualTo(userId);
    }

    @Test
    void extractTenantId_ShouldReturnCorrectTenantId() {
        // Given
        UUID userId = UUID.randomUUID();
        UUID tenantId = UUID.randomUUID();
        String token = jwtService.generateToken(userId, tenantId, "test@example.com", "user");

        // When
        UUID extractedTenantId = jwtService.extractTenantId(token);

        // Then
        assertThat(extractedTenantId).isEqualTo(tenantId);
    }

    @Test
    void isTokenExpired_ShouldReturnFalse_ForFreshToken() {
        // Given
        UUID userId = UUID.randomUUID();
        UUID tenantId = UUID.randomUUID();
        String token = jwtService.generateToken(userId, tenantId, "test@example.com", "user");

        // When
        boolean isExpired = jwtService.isTokenExpired(token);

        // Then
        assertThat(isExpired).isFalse();
    }

    @Test
    void isTokenExpired_ShouldReturnTrue_ForInvalidToken() {
        // Given
        String invalidToken = "invalid.token.here";

        // When
        boolean isExpired = jwtService.isTokenExpired(invalidToken);

        // Then
        assertThat(isExpired).isTrue();
    }
}
