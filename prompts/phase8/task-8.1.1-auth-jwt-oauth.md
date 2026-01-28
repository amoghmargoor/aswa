# Task 8.1.1: Authentication - JWT/OAuth Implementation

## Context

You are implementing authentication for ASWA. This task focuses on JWT token management and OAuth 2.0 integration with identity providers.

## Objective

Create authentication infrastructure that:
1. Implements JWT token generation and validation
2. Supports OAuth 2.0 / OIDC flows
3. Integrates with external identity providers
4. Provides secure token refresh mechanisms
5. Implements proper key rotation

## Requirements

### 1. Create `/libs/common-java/src/main/java/com/aswa/common/auth/JwtTokenProvider.java`
```java
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
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/auth/UserPrincipal.java`
```java
package com.aswa.common.auth;

import java.util.List;
import java.util.Objects;

/**
 * Authenticated user principal.
 */
public class UserPrincipal {

    private final String id;
    private final String tenantId;
    private final String email;
    private final String name;
    private final String role;
    private final List<String> permissions;

    public UserPrincipal(
            String id,
            String tenantId,
            String email,
            String name,
            String role,
            List<String> permissions) {
        this.id = Objects.requireNonNull(id);
        this.tenantId = Objects.requireNonNull(tenantId);
        this.email = Objects.requireNonNull(email);
        this.name = name;
        this.role = Objects.requireNonNull(role);
        this.permissions = permissions != null ? permissions : List.of();
    }

    public String getId() { return id; }
    public String getTenantId() { return tenantId; }
    public String getEmail() { return email; }
    public String getName() { return name; }
    public String getRole() { return role; }
    public List<String> getPermissions() { return permissions; }

    public boolean hasPermission(String permission) {
        return permissions.contains(permission) || permissions.contains("*");
    }

    public boolean hasAnyPermission(String... requiredPermissions) {
        for (String required : requiredPermissions) {
            if (hasPermission(required)) {
                return true;
            }
        }
        return false;
    }

    public boolean hasAllPermissions(String... requiredPermissions) {
        for (String required : requiredPermissions) {
            if (!hasPermission(required)) {
                return false;
            }
        }
        return true;
    }

    public boolean isAdmin() {
        return "admin".equals(role);
    }

    @Override
    public String toString() {
        return "UserPrincipal{" +
            "id='" + id + '\'' +
            ", tenantId='" + tenantId + '\'' +
            ", email='" + email + '\'' +
            ", role='" + role + '\'' +
            '}';
    }
}
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/auth/TokenPair.java`
```java
package com.aswa.common.auth;

/**
 * Access and refresh token pair.
 */
public record TokenPair(
    String accessToken,
    String refreshToken,
    long accessTokenExpiresIn,
    long refreshTokenExpiresIn
) {}
```

### 4. Create `/libs/common-java/src/main/java/com/aswa/common/auth/oauth/OAuthProviderConfig.java`
```java
package com.aswa.common.auth.oauth;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * OAuth provider configuration.
 */
@Component
@ConfigurationProperties(prefix = "oauth")
public class OAuthProviderConfig {

    private Map<String, ProviderSettings> providers = new HashMap<>();

    public Map<String, ProviderSettings> getProviders() {
        return providers;
    }

    public void setProviders(Map<String, ProviderSettings> providers) {
        this.providers = providers;
    }

    public ProviderSettings getProvider(String name) {
        return providers.get(name);
    }

    public static class ProviderSettings {
        private String clientId;
        private String clientSecret;
        private String authorizationUri;
        private String tokenUri;
        private String userInfoUri;
        private String jwksUri;
        private String issuer;
        private String[] scopes;
        private String userNameAttribute;
        private String emailAttribute;
        private boolean enabled;

        public String getClientId() { return clientId; }
        public void setClientId(String clientId) { this.clientId = clientId; }

        public String getClientSecret() { return clientSecret; }
        public void setClientSecret(String clientSecret) { this.clientSecret = clientSecret; }

        public String getAuthorizationUri() { return authorizationUri; }
        public void setAuthorizationUri(String authorizationUri) { this.authorizationUri = authorizationUri; }

        public String getTokenUri() { return tokenUri; }
        public void setTokenUri(String tokenUri) { this.tokenUri = tokenUri; }

        public String getUserInfoUri() { return userInfoUri; }
        public void setUserInfoUri(String userInfoUri) { this.userInfoUri = userInfoUri; }

        public String getJwksUri() { return jwksUri; }
        public void setJwksUri(String jwksUri) { this.jwksUri = jwksUri; }

        public String getIssuer() { return issuer; }
        public void setIssuer(String issuer) { this.issuer = issuer; }

        public String[] getScopes() { return scopes; }
        public void setScopes(String[] scopes) { this.scopes = scopes; }

        public String getUserNameAttribute() { return userNameAttribute; }
        public void setUserNameAttribute(String userNameAttribute) { this.userNameAttribute = userNameAttribute; }

        public String getEmailAttribute() { return emailAttribute; }
        public void setEmailAttribute(String emailAttribute) { this.emailAttribute = emailAttribute; }

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
    }
}
```

### 5. Create `/libs/common-java/src/main/java/com/aswa/common/auth/oauth/OAuthService.java`
```java
package com.aswa.common.auth.oauth;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.TokenPair;
import com.aswa.common.auth.JwtTokenProvider;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * OAuth 2.0 / OIDC service for external identity providers.
 */
@Service
public class OAuthService {

    private static final Logger logger = LoggerFactory.getLogger(OAuthService.class);
    private static final SecureRandom secureRandom = new SecureRandom();

    private final OAuthProviderConfig providerConfig;
    private final JwtTokenProvider jwtTokenProvider;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    // State storage (use Redis in production)
    private final Map<String, OAuthState> stateStore = new ConcurrentHashMap<>();

    public OAuthService(
            OAuthProviderConfig providerConfig,
            JwtTokenProvider jwtTokenProvider,
            RestTemplate restTemplate,
            ObjectMapper objectMapper) {
        this.providerConfig = providerConfig;
        this.jwtTokenProvider = jwtTokenProvider;
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
    }

    /**
     * Generate authorization URL for OAuth provider.
     */
    public AuthorizationUrl generateAuthorizationUrl(
            String provider,
            String redirectUri,
            String tenantId) {

        OAuthProviderConfig.ProviderSettings settings = providerConfig.getProvider(provider);
        if (settings == null || !settings.isEnabled()) {
            throw new IllegalArgumentException("OAuth provider not configured: " + provider);
        }

        String state = generateState();
        String nonce = generateNonce();

        // Store state for verification
        stateStore.put(state, new OAuthState(
            provider,
            tenantId,
            redirectUri,
            nonce,
            System.currentTimeMillis() + 600000 // 10 min expiry
        ));

        StringBuilder urlBuilder = new StringBuilder(settings.getAuthorizationUri());
        urlBuilder.append("?response_type=code");
        urlBuilder.append("&client_id=").append(encode(settings.getClientId()));
        urlBuilder.append("&redirect_uri=").append(encode(redirectUri));
        urlBuilder.append("&scope=").append(encode(String.join(" ", settings.getScopes())));
        urlBuilder.append("&state=").append(encode(state));
        urlBuilder.append("&nonce=").append(encode(nonce));

        return new AuthorizationUrl(urlBuilder.toString(), state);
    }

    /**
     * Handle OAuth callback and exchange code for tokens.
     */
    public TokenPair handleCallback(
            String code,
            String state,
            String redirectUri) {

        // Verify state
        OAuthState oauthState = stateStore.remove(state);
        if (oauthState == null) {
            throw new SecurityException("Invalid or expired state");
        }

        if (System.currentTimeMillis() > oauthState.expiresAt()) {
            throw new SecurityException("State expired");
        }

        OAuthProviderConfig.ProviderSettings settings =
            providerConfig.getProvider(oauthState.provider());

        // Exchange code for tokens
        OAuthTokenResponse tokenResponse = exchangeCodeForTokens(
            settings, code, redirectUri
        );

        // Get user info
        UserInfo userInfo = getUserInfo(settings, tokenResponse.accessToken());

        // Create or update user in database (implementation needed)
        UserPrincipal user = createOrUpdateUser(
            oauthState.tenantId(),
            userInfo,
            oauthState.provider()
        );

        // Generate internal tokens
        return jwtTokenProvider.generateTokenPair(user);
    }

    private OAuthTokenResponse exchangeCodeForTokens(
            OAuthProviderConfig.ProviderSettings settings,
            String code,
            String redirectUri) {

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);
        headers.setBasicAuth(settings.getClientId(), settings.getClientSecret());

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("grant_type", "authorization_code");
        body.add("code", code);
        body.add("redirect_uri", redirectUri);

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        ResponseEntity<JsonNode> response = restTemplate.exchange(
            settings.getTokenUri(),
            HttpMethod.POST,
            request,
            JsonNode.class
        );

        JsonNode responseBody = response.getBody();
        return new OAuthTokenResponse(
            responseBody.get("access_token").asText(),
            responseBody.has("id_token") ? responseBody.get("id_token").asText() : null,
            responseBody.has("refresh_token") ? responseBody.get("refresh_token").asText() : null,
            responseBody.get("expires_in").asLong()
        );
    }

    private UserInfo getUserInfo(
            OAuthProviderConfig.ProviderSettings settings,
            String accessToken) {

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(accessToken);

        HttpEntity<Void> request = new HttpEntity<>(headers);

        ResponseEntity<JsonNode> response = restTemplate.exchange(
            settings.getUserInfoUri(),
            HttpMethod.GET,
            request,
            JsonNode.class
        );

        JsonNode userInfoJson = response.getBody();

        String email = userInfoJson.has(settings.getEmailAttribute())
            ? userInfoJson.get(settings.getEmailAttribute()).asText()
            : userInfoJson.get("email").asText();

        String name = userInfoJson.has(settings.getUserNameAttribute())
            ? userInfoJson.get(settings.getUserNameAttribute()).asText()
            : userInfoJson.has("name") ? userInfoJson.get("name").asText() : email;

        String sub = userInfoJson.get("sub").asText();

        return new UserInfo(sub, email, name);
    }

    private UserPrincipal createOrUpdateUser(
            String tenantId,
            UserInfo userInfo,
            String provider) {
        // TODO: Implement user creation/update in database
        // For now, return a basic principal
        return new UserPrincipal(
            UUID.randomUUID().toString(),
            tenantId,
            userInfo.email(),
            userInfo.name(),
            "user",
            List.of()
        );
    }

    private String generateState() {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String generateNonce() {
        byte[] bytes = new byte[16];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    public record AuthorizationUrl(String url, String state) {}
    public record OAuthState(String provider, String tenantId, String redirectUri, String nonce, long expiresAt) {}
    public record OAuthTokenResponse(String accessToken, String idToken, String refreshToken, long expiresIn) {}
    public record UserInfo(String sub, String email, String name) {}
}
```

### 6. Create `/services/api-gateway/src/main/java/com/aswa/gateway/security/JwtAuthenticationFilter.java`
```java
package com.aswa.gateway.security;

import com.aswa.common.auth.JwtTokenProvider;
import com.aswa.common.auth.UserPrincipal;
import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * JWT authentication filter for API requests.
 */
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final Logger logger = LoggerFactory.getLogger(JwtAuthenticationFilter.class);
    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtTokenProvider jwtTokenProvider;

    public JwtAuthenticationFilter(JwtTokenProvider jwtTokenProvider) {
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {

        try {
            String token = extractToken(request);

            if (token != null) {
                Optional<Claims> claimsOpt = jwtTokenProvider.validateAccessToken(token);

                if (claimsOpt.isPresent()) {
                    Claims claims = claimsOpt.get();
                    UserPrincipal user = jwtTokenProvider.extractUserPrincipal(claims);

                    List<SimpleGrantedAuthority> authorities = user.getPermissions().stream()
                        .map(SimpleGrantedAuthority::new)
                        .collect(Collectors.toList());

                    // Add role as authority
                    authorities.add(new SimpleGrantedAuthority("ROLE_" + user.getRole().toUpperCase()));

                    UsernamePasswordAuthenticationToken authentication =
                        new UsernamePasswordAuthenticationToken(user, null, authorities);

                    SecurityContextHolder.getContext().setAuthentication(authentication);

                    // Set tenant context
                    request.setAttribute("tenantId", user.getTenantId());
                    request.setAttribute("userId", user.getId());

                    logger.debug("Authenticated user: {}", user.getEmail());
                }
            }
        } catch (Exception e) {
            logger.error("Cannot set user authentication: {}", e.getMessage());
        }

        filterChain.doFilter(request, response);
    }

    private String extractToken(HttpServletRequest request) {
        String bearerToken = request.getHeader(AUTHORIZATION_HEADER);

        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith(BEARER_PREFIX)) {
            return bearerToken.substring(BEARER_PREFIX.length());
        }

        return null;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getServletPath();
        return path.startsWith("/health") ||
               path.startsWith("/metrics") ||
               path.startsWith("/api/v1/auth/") ||
               path.startsWith("/oauth2/");
    }
}
```

### 7. Create `/services/api-gateway/src/main/java/com/aswa/gateway/controller/AuthController.java`
```java
package com.aswa.gateway.controller;

import com.aswa.common.auth.JwtTokenProvider;
import com.aswa.common.auth.TokenPair;
import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.oauth.OAuthService;
import io.jsonwebtoken.Claims;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
import java.util.Optional;

/**
 * Authentication controller.
 */
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private static final Logger logger = LoggerFactory.getLogger(AuthController.class);

    private final JwtTokenProvider jwtTokenProvider;
    private final OAuthService oauthService;
    private final AuthService authService;

    public AuthController(
            JwtTokenProvider jwtTokenProvider,
            OAuthService oauthService,
            AuthService authService) {
        this.jwtTokenProvider = jwtTokenProvider;
        this.oauthService = oauthService;
        this.authService = authService;
    }

    /**
     * Login with email and password.
     */
    @PostMapping("/login")
    public ResponseEntity<TokenPair> login(@Valid @RequestBody LoginRequest request) {
        logger.info("Login attempt for: {}", request.email());

        UserPrincipal user = authService.authenticate(
            request.email(),
            request.password(),
            request.tenantId()
        );

        TokenPair tokens = jwtTokenProvider.generateTokenPair(user);

        logger.info("Login successful for: {}", user.getEmail());
        return ResponseEntity.ok(tokens);
    }

    /**
     * Refresh access token using refresh token.
     */
    @PostMapping("/refresh")
    public ResponseEntity<TokenPair> refresh(@Valid @RequestBody RefreshRequest request) {
        Optional<Claims> claimsOpt = jwtTokenProvider.validateRefreshToken(request.refreshToken());

        if (claimsOpt.isEmpty()) {
            return ResponseEntity.status(401).build();
        }

        Claims claims = claimsOpt.get();
        String userId = claims.getSubject();
        String tenantId = claims.get("tenant_id", String.class);

        // Get fresh user data
        UserPrincipal user = authService.getUserById(userId, tenantId);

        TokenPair tokens = jwtTokenProvider.generateTokenPair(user);

        logger.info("Token refreshed for user: {}", user.getEmail());
        return ResponseEntity.ok(tokens);
    }

    /**
     * Initiate OAuth login.
     */
    @GetMapping("/oauth/{provider}")
    public ResponseEntity<Map<String, String>> initiateOAuth(
            @PathVariable String provider,
            @RequestParam String tenantId,
            @RequestParam String redirectUri) {

        OAuthService.AuthorizationUrl authUrl = oauthService.generateAuthorizationUrl(
            provider, redirectUri, tenantId
        );

        return ResponseEntity.ok(Map.of(
            "authorizationUrl", authUrl.url(),
            "state", authUrl.state()
        ));
    }

    /**
     * Handle OAuth callback.
     */
    @PostMapping("/oauth/callback")
    public ResponseEntity<TokenPair> handleOAuthCallback(
            @Valid @RequestBody OAuthCallbackRequest request) {

        TokenPair tokens = oauthService.handleCallback(
            request.code(),
            request.state(),
            request.redirectUri()
        );

        return ResponseEntity.ok(tokens);
    }

    /**
     * Logout (invalidate refresh token).
     */
    @PostMapping("/logout")
    public ResponseEntity<Void> logout(@RequestBody LogoutRequest request) {
        if (request.refreshToken() != null) {
            authService.invalidateRefreshToken(request.refreshToken());
        }
        return ResponseEntity.noContent().build();
    }

    public record LoginRequest(
        @NotBlank String tenantId,
        @NotBlank @Email String email,
        @NotBlank String password
    ) {}

    public record RefreshRequest(
        @NotBlank String refreshToken
    ) {}

    public record OAuthCallbackRequest(
        @NotBlank String code,
        @NotBlank String state,
        @NotBlank String redirectUri
    ) {}

    public record LogoutRequest(String refreshToken) {}
}
```

## Test Requirements

Create tests in `/services/api-gateway/src/test/java/com/aswa/gateway/auth/`:

1. **JwtTokenProviderTest.java** - Test token generation and validation
2. **JwtAuthenticationFilterTest.java** - Test filter behavior
3. **OAuthServiceTest.java** - Test OAuth flow with mocked providers
4. **AuthControllerTest.java** - Integration tests for auth endpoints

## Verification

1. Run tests: `./gradlew test`
2. Test login: `curl -X POST /api/v1/auth/login -d '{"tenantId":"...", "email":"...", "password":"..."}'`
3. Test token refresh
4. Test OAuth initiation and callback
5. Verify token expiration behavior
