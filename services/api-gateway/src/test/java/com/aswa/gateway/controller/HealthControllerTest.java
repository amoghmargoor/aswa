package com.aswa.gateway.controller;

import com.aswa.gateway.AbstractIntegrationTest;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.reactive.server.WebTestClient;

/**
 * Integration tests for HealthController.
 */
class HealthControllerTest extends AbstractIntegrationTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    void health_ShouldReturnUpStatus() {
        webTestClient.get()
                .uri("/health")
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.status").isEqualTo("UP")
                .jsonPath("$.service").isEqualTo("aswa-gateway")
                .jsonPath("$.timestamp").exists();
    }

    @Test
    void ready_ShouldReturnReadyStatus() {
        webTestClient.get()
                .uri("/ready")
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.status").isEqualTo("READY")
                .jsonPath("$.service").isEqualTo("aswa-gateway")
                .jsonPath("$.checks").exists();
    }
}
