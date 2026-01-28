package com.aswa.common.auth.session;

import java.time.Instant;
import java.util.Map;

/**
 * User session data.
 */
public record Session(
    String id,
    String userId,
    String tenantId,
    String refreshTokenId,
    DeviceInfo deviceInfo,
    Instant createdAt,
    Instant lastAccessedAt,
    Instant expiresAt,
    Map<String, Object> metadata
) {

    public boolean isExpired() {
        return Instant.now().isAfter(expiresAt);
    }

    public boolean isActive() {
        return !isExpired();
    }

    public Session withLastAccessed(Instant timestamp) {
        return new Session(
            id, userId, tenantId, refreshTokenId, deviceInfo,
            createdAt, timestamp, expiresAt, metadata
        );
    }

    public Session withExtendedExpiry(Instant newExpiresAt) {
        return new Session(
            id, userId, tenantId, refreshTokenId, deviceInfo,
            createdAt, lastAccessedAt, newExpiresAt, metadata
        );
    }
}
