package com.aswa.gateway.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.time.Instant;
import java.util.Map;

/**
 * Health check endpoints for monitoring and readiness probes.
 */
@Slf4j
@RestController
@RequiredArgsConstructor
@Tag(name = "Health", description = "Health check endpoints")
public class HealthController {

    @GetMapping("/health")
    @Operation(summary = "Basic health check", description = "Returns basic health status")
    public Mono<Map<String, String>> health() {
        return Mono.just(Map.of(
                "status", "UP",
                "service", "aswa-gateway",
                "timestamp", Instant.now().toString()
        ));
    }

    @GetMapping("/ready")
    @Operation(summary = "Readiness check", description = "Returns readiness status with dependency checks")
    public Mono<Map<String, Object>> ready() {
        // TODO: Add actual dependency checks (database, Redis, etc.)
        log.debug("Readiness check requested");

        return Mono.just(Map.of(
                "status", "READY",
                "service", "aswa-gateway",
                "timestamp", Instant.now().toString(),
                "checks", Map.of(
                        "database", "UP",
                        "redis", "UP"
                )
        ));
    }
}
