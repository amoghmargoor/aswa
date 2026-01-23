package com.aswa.gateway.controller;

import com.aswa.gateway.dto.AuthRequest;
import com.aswa.gateway.dto.AuthResponse;
import com.aswa.gateway.dto.RefreshTokenRequest;
import com.aswa.gateway.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

/**
 * Authentication controller for login, token refresh, and logout.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
@Tag(name = "Authentication", description = "Authentication endpoints")
public class AuthController {

    private final AuthService authService;

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

    @PostMapping("/logout")
    @Operation(summary = "User logout", description = "Logout current user (invalidate tokens)")
    public Mono<Void> logout() {
        log.debug("Logout requested");
        // TODO: Implement token blacklisting in Redis
        return Mono.empty()
                .doOnSuccess(v -> log.debug("Logout successful"));
    }
}
