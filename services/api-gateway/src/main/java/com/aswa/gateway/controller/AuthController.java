package com.aswa.gateway.controller;

import com.aswa.common.auth.JwtTokenProvider;
import com.aswa.common.auth.TokenPair;
import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.oauth.OAuthService;
import com.aswa.gateway.dto.AuthRequest;
import com.aswa.gateway.dto.AuthResponse;
import com.aswa.gateway.dto.RefreshTokenRequest;
import com.aswa.gateway.service.AuthService;
import io.jsonwebtoken.Claims;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.Map;
import java.util.Optional;

/**
 * Authentication controller for login, token refresh, OAuth, and logout.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/auth")
@Tag(name = "Authentication", description = "Authentication endpoints")
public class AuthController {

    private final AuthService authService;
    private final JwtTokenProvider jwtTokenProvider;
    private final OAuthService oauthService;

    public AuthController(
            AuthService authService,
            JwtTokenProvider jwtTokenProvider,
            OAuthService oauthService) {
        this.authService = authService;
        this.jwtTokenProvider = jwtTokenProvider;
        this.oauthService = oauthService;
    }

    @PostMapping("/login")
    @Operation(summary = "User login", description = "Authenticate user with email and password")
    public Mono<AuthResponse> login(@Valid @RequestBody AuthRequest request) {
        log.info("Login attempt for user: {}", request.email());
        return authService.login(request)
                .doOnSuccess(response -> log.info("Login successful for user: {}", request.email()))
                .doOnError(error -> log.warn("Login failed for user: {}", request.email()));
    }

    @PostMapping("/refresh")
    @Operation(summary = "Refresh access token", description = "Get new access token using refresh token")
    public Mono<AuthResponse> refresh(@Valid @RequestBody RefreshTokenRequest request) {
        log.debug("Token refresh requested");
        return authService.refresh(request)
                .doOnSuccess(response -> log.debug("Token refreshed successfully"))
                .doOnError(error -> log.warn("Token refresh failed"));
    }

    @GetMapping("/oauth/{provider}")
    @Operation(summary = "Initiate OAuth login", description = "Get OAuth authorization URL for provider")
    public ResponseEntity<Map<String, String>> initiateOAuth(
            @PathVariable String provider,
            @RequestParam String tenantId,
            @RequestParam String redirectUri) {

        log.info("OAuth initiation for provider: {}", provider);
        OAuthService.AuthorizationUrl authUrl = oauthService.generateAuthorizationUrl(
            provider, redirectUri, tenantId
        );

        return ResponseEntity.ok(Map.of(
            "authorizationUrl", authUrl.url(),
            "state", authUrl.state()
        ));
    }

    @PostMapping("/oauth/callback")
    @Operation(summary = "Handle OAuth callback", description = "Exchange OAuth code for tokens")
    public ResponseEntity<TokenPair> handleOAuthCallback(
            @Valid @RequestBody OAuthCallbackRequest request) {

        log.info("OAuth callback received");
        TokenPair tokens = oauthService.handleCallback(
            request.code(),
            request.state(),
            request.redirectUri()
        );

        return ResponseEntity.ok(tokens);
    }

    @PostMapping("/logout")
    @Operation(summary = "User logout", description = "Logout current user (invalidate tokens)")
    public Mono<Void> logout(@RequestBody(required = false) LogoutRequest request) {
        log.debug("Logout requested");
        if (request != null && request.refreshToken() != null) {
            authService.invalidateRefreshToken(request.refreshToken());
        }
        return Mono.empty()
                .doOnSuccess(v -> log.debug("Logout successful"));
    }

    public record OAuthCallbackRequest(
        @NotBlank String code,
        @NotBlank String state,
        @NotBlank String redirectUri
    ) {}

    public record LogoutRequest(String refreshToken) {}
}
