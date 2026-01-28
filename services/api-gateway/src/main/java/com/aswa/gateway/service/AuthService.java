package com.aswa.gateway.service;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.gateway.dto.AuthRequest;
import com.aswa.gateway.dto.AuthResponse;
import com.aswa.gateway.dto.RefreshTokenRequest;
import reactor.core.publisher.Mono;

/**
 * Authentication service interface.
 */
public interface AuthService {

    /**
     * Authenticate user with email and password.
     *
     * @param request authentication request
     * @return authentication response with tokens
     */
    Mono<AuthResponse> login(AuthRequest request);

    /**
     * Refresh access token using refresh token.
     *
     * @param request refresh token request
     * @return new authentication response
     */
    Mono<AuthResponse> refresh(RefreshTokenRequest request);

    /**
     * Authenticate user with email and password (blocking).
     *
     * @param email user email
     * @param password user password
     * @param tenantId tenant ID
     * @return authenticated user principal
     */
    UserPrincipal authenticate(String email, String password, String tenantId);

    /**
     * Get user by ID.
     *
     * @param userId user ID
     * @param tenantId tenant ID
     * @return user principal
     */
    UserPrincipal getUserById(String userId, String tenantId);

    /**
     * Invalidate refresh token.
     *
     * @param refreshToken the refresh token to invalidate
     */
    void invalidateRefreshToken(String refreshToken);
}
