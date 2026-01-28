package com.aswa.common.auth;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import io.jsonwebtoken.security.SignatureException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;

/**
 * JWT token provider for authentication.
 */
@Component
public class JwtTokenProvider {

    private static final Logger logger = LoggerFactory.getLogger(JwtTokenProvider.class);

    private final SecretKey accessTokenKey;
    private final SecretKey refreshTokenKey;
    private final long accessTokenValidityMs;
    private final long refreshTokenValidityMs;
    private final String issuer;

    public JwtTokenProvider(
            @Value("${jwt.access-token.secret}") String accessTokenSecret,
            @Value("${jwt.refresh-token.secret}") String refreshTokenSecret,
            @Value("${jwt.access-token.validity-ms:900000}") long accessTokenValidityMs,
            @Value("${jwt.refresh-token.validity-ms:604800000}") long refreshTokenValidityMs,
            @Value("${jwt.issuer:aswa}") String issuer) {

        this.accessTokenKey = Keys.hmacShaKeyFor(
            padOrTruncateKey(accessTokenSecret).getBytes(StandardCharsets.UTF_8)
        );
        this.refreshTokenKey = Keys.hmacShaKeyFor(
            padOrTruncateKey(refreshTokenSecret).getBytes(StandardCharsets.UTF_8)
        );
        this.accessTokenValidityMs = accessTokenValidityMs;
        this.refreshTokenValidityMs = refreshTokenValidityMs;
        this.issuer = issuer;
    }

    private String padOrTruncateKey(String key) {
        if (key.length() >= 64) {
            return key.substring(0, 64);
        }
        return String.format("%-64s", key).replace(' ', '0');
    }

    /**
     * Generate access token for user.
     */
    public TokenPair generateTokenPair(UserPrincipal user) {
        String accessToken = generateAccessToken(user);
        String refreshToken = generateRefreshToken(user);

        return new TokenPair(
            accessToken,
            refreshToken,
            accessTokenValidityMs / 1000,
            refreshTokenValidityMs / 1000
        );
    }

    /**
     * Generate access token.
     */
    public String generateAccessToken(UserPrincipal user) {
        Instant now = Instant.now();
        Instant expiry = now.plusMillis(accessTokenValidityMs);

        return Jwts.builder()
            .setSubject(user.getId())
            .setIssuer(issuer)
            .setIssuedAt(Date.from(now))
            .setExpiration(Date.from(expiry))
            .claim("tenant_id", user.getTenantId())
            .claim("email", user.getEmail())
            .claim("name", user.getName())
            .claim("role", user.getRole())
            .claim("permissions", user.getPermissions())
            .claim("type", "access")
            .signWith(accessTokenKey, SignatureAlgorithm.HS512)
            .compact();
    }

    /**
     * Generate refresh token.
     */
    public String generateRefreshToken(UserPrincipal user) {
        Instant now = Instant.now();
        Instant expiry = now.plusMillis(refreshTokenValidityMs);
        String tokenId = UUID.randomUUID().toString();

        return Jwts.builder()
            .setId(tokenId)
            .setSubject(user.getId())
            .setIssuer(issuer)
            .setIssuedAt(Date.from(now))
            .setExpiration(Date.from(expiry))
            .claim("tenant_id", user.getTenantId())
            .claim("type", "refresh")
            .signWith(refreshTokenKey, SignatureAlgorithm.HS512)
            .compact();
    }

    /**
     * Validate access token.
     */
    public Optional<Claims> validateAccessToken(String token) {
        return validateToken(token, accessTokenKey, "access");
    }

    /**
     * Validate refresh token.
     */
    public Optional<Claims> validateRefreshToken(String token) {
        return validateToken(token, refreshTokenKey, "refresh");
    }

    private Optional<Claims> validateToken(String token, SecretKey key, String expectedType) {
        try {
            Claims claims = Jwts.parserBuilder()
                .setSigningKey(key)
                .requireIssuer(issuer)
                .build()
                .parseClaimsJws(token)
                .getBody();

            String tokenType = claims.get("type", String.class);
            if (!expectedType.equals(tokenType)) {
                logger.warn("Token type mismatch: expected={}, actual={}", expectedType, tokenType);
                return Optional.empty();
            }

            return Optional.of(claims);

        } catch (ExpiredJwtException e) {
            logger.debug("Token expired: {}", e.getMessage());
        } catch (UnsupportedJwtException e) {
            logger.warn("Unsupported JWT: {}", e.getMessage());
        } catch (MalformedJwtException e) {
            logger.warn("Malformed JWT: {}", e.getMessage());
        } catch (SignatureException e) {
            logger.warn("Invalid JWT signature: {}", e.getMessage());
        } catch (IllegalArgumentException e) {
            logger.warn("JWT claims string is empty: {}", e.getMessage());
        }

        return Optional.empty();
    }

    /**
     * Extract user principal from claims.
     */
    @SuppressWarnings("unchecked")
    public UserPrincipal extractUserPrincipal(Claims claims) {
        return new UserPrincipal(
            claims.getSubject(),
            claims.get("tenant_id", String.class),
            claims.get("email", String.class),
            claims.get("name", String.class),
            claims.get("role", String.class),
            (List<String>) claims.get("permissions", List.class)
        );
    }

    /**
     * Get token expiration time.
     */
    public Optional<Date> getExpiration(String token) {
        try {
            Claims claims = Jwts.parserBuilder()
                .setSigningKey(accessTokenKey)
                .build()
                .parseClaimsJws(token)
                .getBody();
            return Optional.of(claims.getExpiration());
        } catch (Exception e) {
            return Optional.empty();
        }
    }
}
