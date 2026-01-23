package com.aswa.gateway.security;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for TenantContext.
 */
class TenantContextTest {

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void setAndGet_ShouldWorkCorrectly() {
        // Given
        UUID tenantId = UUID.randomUUID();
        UUID userId = UUID.randomUUID();
        Set<String> roles = Set.of("ROLE_ADMIN", "ROLE_USER");
        TenantContext context = new TenantContext(tenantId, userId, roles);

        // When
        TenantContext.set(context);
        TenantContext retrieved = TenantContext.get();

        // Then
        assertThat(retrieved).isNotNull();
        assertThat(retrieved.tenantId()).isEqualTo(tenantId);
        assertThat(retrieved.userId()).isEqualTo(userId);
        assertThat(retrieved.roles()).containsExactlyInAnyOrderElementsOf(roles);
    }

    @Test
    void clear_ShouldRemoveContext() {
        // Given
        TenantContext context = new TenantContext(UUID.randomUUID(), UUID.randomUUID(), Set.of());
        TenantContext.set(context);

        // When
        TenantContext.clear();

        // Then
        assertThat(TenantContext.get()).isNull();
    }

    @Test
    void hasRole_ShouldReturnTrue_WhenRoleExists() {
        // Given
        TenantContext context = new TenantContext(
                UUID.randomUUID(),
                UUID.randomUUID(),
                Set.of("ROLE_ADMIN", "ROLE_USER")
        );

        // When / Then
        assertThat(context.hasRole("ROLE_ADMIN")).isTrue();
        assertThat(context.hasRole("ROLE_USER")).isTrue();
    }

    @Test
    void hasRole_ShouldReturnFalse_WhenRoleDoesNotExist() {
        // Given
        TenantContext context = new TenantContext(
                UUID.randomUUID(),
                UUID.randomUUID(),
                Set.of("ROLE_USER")
        );

        // When / Then
        assertThat(context.hasRole("ROLE_ADMIN")).isFalse();
    }

    @Test
    void getCurrentTenantId_ShouldReturnTenantId_WhenContextIsSet() {
        // Given
        UUID tenantId = UUID.randomUUID();
        TenantContext context = new TenantContext(tenantId, UUID.randomUUID(), Set.of());
        TenantContext.set(context);

        // When
        UUID retrieved = TenantContext.getCurrentTenantId();

        // Then
        assertThat(retrieved).isEqualTo(tenantId);
    }

    @Test
    void getCurrentTenantId_ShouldThrowException_WhenContextNotSet() {
        // When / Then
        assertThatThrownBy(TenantContext::getCurrentTenantId)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("TenantContext not set");
    }

    @Test
    void getCurrentUserId_ShouldReturnUserId_WhenContextIsSet() {
        // Given
        UUID userId = UUID.randomUUID();
        TenantContext context = new TenantContext(UUID.randomUUID(), userId, Set.of());
        TenantContext.set(context);

        // When
        UUID retrieved = TenantContext.getCurrentUserId();

        // Then
        assertThat(retrieved).isEqualTo(userId);
    }

    @Test
    void getCurrentUserId_ShouldThrowException_WhenContextNotSet() {
        // When / Then
        assertThatThrownBy(TenantContext::getCurrentUserId)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("TenantContext not set");
    }
}
