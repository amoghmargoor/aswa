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
