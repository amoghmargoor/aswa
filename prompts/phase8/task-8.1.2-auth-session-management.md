# Task 8.1.2: Authentication - Session Management

## Context

You are implementing authentication for ASWA. JWT/OAuth is complete. Now we need secure session management with Redis-backed storage.

## Objective

Create session management that:
1. Implements secure session storage in Redis
2. Supports concurrent session limits
3. Enables session revocation
4. Tracks session metadata (device, IP, location)
5. Implements session timeout policies

## Requirements

### 1. Create `/libs/common-java/src/main/java/com/aswa/common/auth/session/Session.java`
```java
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
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/auth/session/DeviceInfo.java`
```java
package com.aswa.common.auth.session;

/**
 * Device information for session tracking.
 */
public record DeviceInfo(
    String userAgent,
    String ipAddress,
    String deviceType,
    String browser,
    String os,
    String country,
    String city
) {

    public static DeviceInfo fromRequest(String userAgent, String ipAddress) {
        // Parse user agent (use library like ua-parser in production)
        String deviceType = detectDeviceType(userAgent);
        String browser = detectBrowser(userAgent);
        String os = detectOS(userAgent);

        return new DeviceInfo(
            userAgent,
            ipAddress,
            deviceType,
            browser,
            os,
            null, // Geo lookup needed
            null
        );
    }

    private static String detectDeviceType(String userAgent) {
        if (userAgent == null) return "unknown";
        String ua = userAgent.toLowerCase();
        if (ua.contains("mobile") || ua.contains("android") || ua.contains("iphone")) {
            return "mobile";
        } else if (ua.contains("tablet") || ua.contains("ipad")) {
            return "tablet";
        }
        return "desktop";
    }

    private static String detectBrowser(String userAgent) {
        if (userAgent == null) return "unknown";
        String ua = userAgent.toLowerCase();
        if (ua.contains("chrome") && !ua.contains("edg")) return "Chrome";
        if (ua.contains("firefox")) return "Firefox";
        if (ua.contains("safari") && !ua.contains("chrome")) return "Safari";
        if (ua.contains("edg")) return "Edge";
        return "Other";
    }

    private static String detectOS(String userAgent) {
        if (userAgent == null) return "unknown";
        String ua = userAgent.toLowerCase();
        if (ua.contains("windows")) return "Windows";
        if (ua.contains("mac os")) return "macOS";
        if (ua.contains("linux")) return "Linux";
        if (ua.contains("android")) return "Android";
        if (ua.contains("iphone") || ua.contains("ipad")) return "iOS";
        return "Other";
    }

    public String getDisplayName() {
        return String.format("%s on %s (%s)", browser, os, deviceType);
    }
}
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/auth/session/SessionManager.java`
```java
package com.aswa.common.auth.session;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * Redis-backed session manager.
 */
@Component
public class SessionManager {

    private static final Logger logger = LoggerFactory.getLogger(SessionManager.class);

    private static final String SESSION_KEY_PREFIX = "session:";
    private static final String USER_SESSIONS_KEY_PREFIX = "user_sessions:";
    private static final String REVOKED_TOKENS_KEY_PREFIX = "revoked_tokens:";

    private final RedisTemplate<String, String> redisTemplate;
    private final ObjectMapper objectMapper;
    private final int maxConcurrentSessions;
    private final Duration sessionTimeout;
    private final Duration idleTimeout;

    public SessionManager(
            RedisTemplate<String, String> redisTemplate,
            ObjectMapper objectMapper,
            @Value("${session.max-concurrent:5}") int maxConcurrentSessions,
            @Value("${session.timeout-hours:168}") int sessionTimeoutHours,
            @Value("${session.idle-timeout-hours:24}") int idleTimeoutHours) {
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.maxConcurrentSessions = maxConcurrentSessions;
        this.sessionTimeout = Duration.ofHours(sessionTimeoutHours);
        this.idleTimeout = Duration.ofHours(idleTimeoutHours);
    }

    /**
     * Create a new session.
     */
    public Session createSession(
            String userId,
            String tenantId,
            String refreshTokenId,
            DeviceInfo deviceInfo) {

        String sessionId = generateSessionId();
        Instant now = Instant.now();

        Session session = new Session(
            sessionId,
            userId,
            tenantId,
            refreshTokenId,
            deviceInfo,
            now,
            now,
            now.plus(sessionTimeout),
            new HashMap<>()
        );

        // Check and enforce concurrent session limit
        enforceConcurrentSessionLimit(userId, tenantId);

        // Store session
        saveSession(session);

        // Add to user's session list
        String userSessionsKey = USER_SESSIONS_KEY_PREFIX + tenantId + ":" + userId;
        redisTemplate.opsForSet().add(userSessionsKey, sessionId);

        logger.info("Created session {} for user {} from {}",
            sessionId, userId, deviceInfo.getDisplayName());

        return session;
    }

    /**
     * Get session by ID.
     */
    public Optional<Session> getSession(String sessionId) {
        String key = SESSION_KEY_PREFIX + sessionId;
        String sessionJson = redisTemplate.opsForValue().get(key);

        if (sessionJson == null) {
            return Optional.empty();
        }

        try {
            Session session = objectMapper.readValue(sessionJson, Session.class);

            if (session.isExpired()) {
                deleteSession(sessionId);
                return Optional.empty();
            }

            return Optional.of(session);
        } catch (JsonProcessingException e) {
            logger.error("Failed to deserialize session: {}", e.getMessage());
            return Optional.empty();
        }
    }

    /**
     * Update session last accessed time.
     */
    public void touchSession(String sessionId) {
        getSession(sessionId).ifPresent(session -> {
            Instant now = Instant.now();

            // Check idle timeout
            if (now.isAfter(session.lastAccessedAt().plus(idleTimeout))) {
                logger.info("Session {} expired due to idle timeout", sessionId);
                deleteSession(sessionId);
                return;
            }

            Session updated = session.withLastAccessed(now);
            saveSession(updated);
        });
    }

    /**
     * Get all sessions for a user.
     */
    public List<Session> getUserSessions(String userId, String tenantId) {
        String userSessionsKey = USER_SESSIONS_KEY_PREFIX + tenantId + ":" + userId;
        Set<String> sessionIds = redisTemplate.opsForSet().members(userSessionsKey);

        if (sessionIds == null || sessionIds.isEmpty()) {
            return List.of();
        }

        return sessionIds.stream()
            .map(this::getSession)
            .filter(Optional::isPresent)
            .map(Optional::get)
            .sorted((a, b) -> b.lastAccessedAt().compareTo(a.lastAccessedAt()))
            .collect(Collectors.toList());
    }

    /**
     * Revoke a specific session.
     */
    public void revokeSession(String sessionId) {
        getSession(sessionId).ifPresent(session -> {
            // Add refresh token to revoked list
            if (session.refreshTokenId() != null) {
                revokeRefreshToken(session.refreshTokenId(), session.expiresAt());
            }

            deleteSession(sessionId);

            logger.info("Revoked session {} for user {}", sessionId, session.userId());
        });
    }

    /**
     * Revoke all sessions for a user.
     */
    public void revokeAllUserSessions(String userId, String tenantId) {
        List<Session> sessions = getUserSessions(userId, tenantId);

        for (Session session : sessions) {
            revokeSession(session.id());
        }

        logger.info("Revoked {} sessions for user {}", sessions.size(), userId);
    }

    /**
     * Revoke all sessions except current.
     */
    public void revokeOtherSessions(String userId, String tenantId, String currentSessionId) {
        List<Session> sessions = getUserSessions(userId, tenantId);

        int revokedCount = 0;
        for (Session session : sessions) {
            if (!session.id().equals(currentSessionId)) {
                revokeSession(session.id());
                revokedCount++;
            }
        }

        logger.info("Revoked {} other sessions for user {}", revokedCount, userId);
    }

    /**
     * Check if a refresh token is revoked.
     */
    public boolean isRefreshTokenRevoked(String tokenId) {
        String key = REVOKED_TOKENS_KEY_PREFIX + tokenId;
        return Boolean.TRUE.equals(redisTemplate.hasKey(key));
    }

    /**
     * Revoke a refresh token.
     */
    public void revokeRefreshToken(String tokenId, Instant expiresAt) {
        String key = REVOKED_TOKENS_KEY_PREFIX + tokenId;
        long ttlSeconds = Duration.between(Instant.now(), expiresAt).getSeconds();

        if (ttlSeconds > 0) {
            redisTemplate.opsForValue().set(key, "revoked", ttlSeconds, TimeUnit.SECONDS);
        }
    }

    private void enforceConcurrentSessionLimit(String userId, String tenantId) {
        List<Session> sessions = getUserSessions(userId, tenantId);

        if (sessions.size() >= maxConcurrentSessions) {
            // Remove oldest sessions
            int toRemove = sessions.size() - maxConcurrentSessions + 1;

            List<Session> sorted = sessions.stream()
                .sorted(Comparator.comparing(Session::lastAccessedAt))
                .limit(toRemove)
                .toList();

            for (Session session : sorted) {
                revokeSession(session.id());
                logger.info("Evicted oldest session {} due to concurrent limit", session.id());
            }
        }
    }

    private void saveSession(Session session) {
        try {
            String key = SESSION_KEY_PREFIX + session.id();
            String json = objectMapper.writeValueAsString(session);

            long ttlSeconds = Duration.between(Instant.now(), session.expiresAt()).getSeconds();
            redisTemplate.opsForValue().set(key, json, ttlSeconds, TimeUnit.SECONDS);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize session", e);
        }
    }

    private void deleteSession(String sessionId) {
        // Get session to find user
        String key = SESSION_KEY_PREFIX + sessionId;
        String sessionJson = redisTemplate.opsForValue().get(key);

        if (sessionJson != null) {
            try {
                Session session = objectMapper.readValue(sessionJson, Session.class);

                // Remove from user's session list
                String userSessionsKey = USER_SESSIONS_KEY_PREFIX +
                    session.tenantId() + ":" + session.userId();
                redisTemplate.opsForSet().remove(userSessionsKey, sessionId);
            } catch (JsonProcessingException e) {
                logger.error("Failed to deserialize session for cleanup: {}", e.getMessage());
            }
        }

        // Delete session
        redisTemplate.delete(key);
    }

    private String generateSessionId() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}
```

### 4. Create `/libs/common-java/src/main/java/com/aswa/common/auth/session/SessionService.java`
```java
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
```

### 5. Create `/services/api-gateway/src/main/java/com/aswa/gateway/controller/SessionController.java`
```java
package com.aswa.gateway.controller;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.session.SessionService;
import com.aswa.common.auth.session.SessionService.SessionInfo;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Session management controller.
 */
@RestController
@RequestMapping("/api/v1/sessions")
public class SessionController {

    private final SessionService sessionService;

    public SessionController(SessionService sessionService) {
        this.sessionService = sessionService;
    }

    /**
     * List active sessions for current user.
     */
    @GetMapping
    public ResponseEntity<List<SessionInfo>> listSessions(
            @AuthenticationPrincipal UserPrincipal user) {

        List<SessionInfo> sessions = sessionService.getActiveSessions(
            user.getId(),
            user.getTenantId()
        );

        return ResponseEntity.ok(sessions);
    }

    /**
     * Terminate a specific session.
     */
    @DeleteMapping("/{sessionId}")
    public ResponseEntity<Void> terminateSession(
            @PathVariable String sessionId,
            @AuthenticationPrincipal UserPrincipal user) {

        sessionService.terminateSession(
            sessionId,
            user.getId(),
            user.getTenantId()
        );

        return ResponseEntity.noContent().build();
    }

    /**
     * Terminate all other sessions.
     */
    @PostMapping("/terminate-others")
    public ResponseEntity<Void> terminateOtherSessions(
            @RequestHeader("X-Session-Id") String currentSessionId,
            @AuthenticationPrincipal UserPrincipal user) {

        sessionService.terminateOtherSessions(
            currentSessionId,
            user.getId(),
            user.getTenantId()
        );

        return ResponseEntity.noContent().build();
    }

    /**
     * Terminate all sessions (logout everywhere).
     */
    @PostMapping("/terminate-all")
    public ResponseEntity<Void> terminateAllSessions(
            @AuthenticationPrincipal UserPrincipal user) {

        sessionService.terminateAllSessions(
            user.getId(),
            user.getTenantId()
        );

        return ResponseEntity.noContent().build();
    }
}
```

### 6. Update application configuration

Add to `/services/api-gateway/src/main/resources/application.yaml`:
```yaml
session:
  max-concurrent: 5
  timeout-hours: 168  # 7 days
  idle-timeout-hours: 24

spring:
  redis:
    host: ${REDIS_HOST:localhost}
    port: ${REDIS_PORT:6379}
    password: ${REDIS_PASSWORD:}
    ssl: ${REDIS_SSL:false}
```

## Test Requirements

Create tests in `/services/api-gateway/src/test/java/com/aswa/gateway/session/`:

1. **SessionManagerTest.java** - Test Redis session operations
2. **SessionServiceTest.java** - Test session lifecycle
3. **SessionControllerTest.java** - Test API endpoints
4. **ConcurrentSessionTest.java** - Test session limits

## Verification

1. Run tests: `./gradlew test`
2. Create session and verify in Redis
3. Test concurrent session eviction
4. Test session revocation
5. Verify idle timeout behavior
