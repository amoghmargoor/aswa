package com.aswa.common.auth.session;

import com.aswa.common.auth.UserPrincipal;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Session management service.
 */
@Service
public class SessionService {

    private final SessionManager sessionManager;

    public SessionService(SessionManager sessionManager) {
        this.sessionManager = sessionManager;
    }

    /**
     * Create session after successful authentication.
     */
    public Session createSession(
            UserPrincipal user,
            String refreshTokenId,
            String userAgent,
            String ipAddress) {

        DeviceInfo deviceInfo = DeviceInfo.fromRequest(userAgent, ipAddress);

        return sessionManager.createSession(
            user.getId(),
            user.getTenantId(),
            refreshTokenId,
            deviceInfo
        );
    }

    /**
     * Validate and refresh session.
     */
    public boolean validateSession(String sessionId) {
        return sessionManager.getSession(sessionId)
            .map(session -> {
                sessionManager.touchSession(sessionId);
                return true;
            })
            .orElse(false);
    }

    /**
     * Get active sessions for user.
     */
    public List<SessionInfo> getActiveSessions(String userId, String tenantId) {
        return sessionManager.getUserSessions(userId, tenantId).stream()
            .map(this::toSessionInfo)
            .toList();
    }

    /**
     * Terminate specific session.
     */
    public void terminateSession(String sessionId, String userId, String tenantId) {
        sessionManager.getSession(sessionId)
            .filter(s -> s.userId().equals(userId) && s.tenantId().equals(tenantId))
            .ifPresent(s -> sessionManager.revokeSession(sessionId));
    }

    /**
     * Terminate all other sessions.
     */
    public void terminateOtherSessions(String currentSessionId, String userId, String tenantId) {
        sessionManager.revokeOtherSessions(userId, tenantId, currentSessionId);
    }

    /**
     * Terminate all sessions (force logout everywhere).
     */
    public void terminateAllSessions(String userId, String tenantId) {
        sessionManager.revokeAllUserSessions(userId, tenantId);
    }

    /**
     * Check if refresh token is still valid (not revoked).
     */
    public boolean isRefreshTokenValid(String tokenId) {
        return !sessionManager.isRefreshTokenRevoked(tokenId);
    }

    private SessionInfo toSessionInfo(Session session) {
        return new SessionInfo(
            session.id(),
            session.deviceInfo().getDisplayName(),
            session.deviceInfo().ipAddress(),
            session.deviceInfo().country(),
            session.createdAt(),
            session.lastAccessedAt(),
            session.deviceInfo().deviceType()
        );
    }

    public record SessionInfo(
        String sessionId,
        String device,
        String ipAddress,
        String location,
        java.time.Instant createdAt,
        java.time.Instant lastActiveAt,
        String deviceType
    ) {}
}
