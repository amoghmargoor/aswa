package com.aswa.gateway.controller;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.session.SessionService;
import com.aswa.common.auth.session.SessionService.SessionInfo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Session management controller.
 */
@RestController
@RequestMapping("/api/v1/sessions")
@Tag(name = "Sessions", description = "Session management endpoints")
public class SessionController {

    private final SessionService sessionService;

    public SessionController(SessionService sessionService) {
        this.sessionService = sessionService;
    }

    /**
     * List active sessions for current user.
     */
    @GetMapping
    @Operation(summary = "List sessions", description = "Get all active sessions for current user")
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
    @Operation(summary = "Terminate session", description = "Terminate a specific session")
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
    @Operation(summary = "Terminate other sessions", description = "Terminate all sessions except current")
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
    @Operation(summary = "Terminate all sessions", description = "Logout from all devices")
    public ResponseEntity<Void> terminateAllSessions(
            @AuthenticationPrincipal UserPrincipal user) {

        sessionService.terminateAllSessions(
            user.getId(),
            user.getTenantId()
        );

        return ResponseEntity.noContent().build();
    }
}
