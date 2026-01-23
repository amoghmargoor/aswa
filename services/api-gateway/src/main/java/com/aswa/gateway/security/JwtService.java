package com.aswa.gateway.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.Map;
import java.util.UUID;

/**
 * JWT token service for generation and validation.
 *
 * Handles:
 * - Access token generation with user and tenant claims
 * - Refresh token generation
 * - Token validation and claims extraction
 */
@Slf4j
@Service
public class JwtService {

    private final SecretKey secretKey;
    private final long expirationMs;
    private final long refreshExpirationMs;

    public JwtService(
            @Value("${jwt.secret}") String secret,
            @Value("${jwt.expiration:3600}") long expiration,
            @Value("${jwt.refresh-expiration:604800}") long refreshExpiration) {
        this.secretKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expirationMs = expiration * 1000; // Convert seconds to milliseconds
        this.refreshExpirationMs = refreshExpiration * 1000;
        log.info("JwtService initialized with expiration={}s, refreshExpiration={}s",
                expiration, refreshExpiration);
    }

    /**
     * Generate access token for user.
     *
     * @param userId user ID
     * @param tenantId tenant ID
     * @param email user email
     * @param roles user roles
     * @return JWT token
     */
    public String generateToken(UUID userId, UUID tenantId, String email, String roles) {
        Instant now = Instant.now();
        Instant expiration = now.plus(expirationMs, ChronoUnit.MILLIS);

        String token = Jwts.builder()
                .subject(userId.toString())
                .claim("tenant_id", tenantId.toString())
                .claim("email", email)
                .claim("roles", roles)
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiration))
                .signWith(secretKey)
                .compact();

        log.debug("Generated access token for user={}, tenant={}", userId, tenantId);
        return token;
    }

    /**
     * Generate refresh token for user.
     *
     * @param userId user ID
     * @param tenantId tenant ID
     * @return refresh token
     */
    public String generateRefreshToken(UUID userId, UUID tenantId) {
        Instant now = Instant.now();
        Instant expiration = now.plus(refreshExpirationMs, ChronoUnit.MILLIS);

        String token = Jwts.builder()
                .subject(userId.toString())
                .claim("tenant_id", tenantId.toString())
                .claim("type", "refresh")
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiration))
                .signWith(secretKey)
                .compact();

        log.debug("Generated refresh token for user={}, tenant={}", userId, tenantId);
        return token;
    }

    /**
     * Validate token and extract claims.
     *
     * @param token JWT token
     * @return claims if valid
     */
    public Mono<Claims> validateToken(String token) {
        return Mono.fromCallable(() -> {
            try {
                Claims claims = Jwts.parser()
                        .verifyWith(secretKey)
                        .build()
                        .parseSignedClaims(token)
                        .getPayload();

                log.debug("Token validated successfully for user={}", claims.getSubject());
                return claims;
            } catch (Exception e) {
                log.warn("Token validation failed: {}", e.getMessage());
                throw new IllegalArgumentException("Invalid JWT token", e);
            }
        });
    }

    /**
     * Extract user ID from token.
     *
     * @param token JWT token
     * @return user ID
     */
    public UUID extractUserId(String token) {
        Claims claims = Jwts.parser()
                .verifyWith(secretKey)
                .build()
                .parseSignedClaims(token)
                .getPayload();
        return UUID.fromString(claims.getSubject());
    }

    /**
     * Extract tenant ID from token.
     *
     * @param token JWT token
     * @return tenant ID
     */
    public UUID extractTenantId(String token) {
        Claims claims = Jwts.parser()
                .verifyWith(secretKey)
                .build()
                .parseSignedClaims(token)
                .getPayload();
        return UUID.fromString(claims.get("tenant_id", String.class));
    }

    /**
     * Check if token is expired.
     *
     * @param token JWT token
     * @return true if expired
     */
    public boolean isTokenExpired(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(secretKey)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            return claims.getExpiration().before(new Date());
        } catch (Exception e) {
            return true;
        }
    }
}
