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
