package com.aswa.gateway.service;

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
}
