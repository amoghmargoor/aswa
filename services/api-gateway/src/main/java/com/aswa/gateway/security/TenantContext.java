package com.aswa.gateway.security;

import java.util.Set;
import java.util.UUID;

/**
 * Thread-local tenant context for multi-tenant data isolation.
 *
 * Stores tenant ID, user ID, and roles for the current request.
 * Automatically populated by TenantContextFilter from JWT claims.
 */
public record TenantContext(UUID tenantId, UUID userId, Set<String> roles) {

    private static final ThreadLocal<TenantContext> CONTEXT = new ThreadLocal<>();

    /**
     * Set tenant context for current thread.
     *
     * @param ctx tenant context
     */
    public static void set(TenantContext ctx) {
        CONTEXT.set(ctx);
    }

    /**
     * Get tenant context for current thread.
     *
     * @return tenant context or null if not set
     */
    public static TenantContext get() {
        return CONTEXT.get();
    }

    /**
     * Clear tenant context for current thread.
     * Should be called in finally block to prevent leaks.
     */
    public static void clear() {
        CONTEXT.remove();
    }

    /**
     * Check if current user has specified role.
     *
     * @param role role to check
     * @return true if user has role
     */
    public boolean hasRole(String role) {
        return roles != null && roles.contains(role);
    }

    /**
     * Get current tenant ID.
     *
     * @return tenant ID
     * @throws IllegalStateException if context not set
     */
    public static UUID getCurrentTenantId() {
        TenantContext ctx = get();
        if (ctx == null) {
            throw new IllegalStateException("TenantContext not set");
        }
        return ctx.tenantId();
    }

    /**
     * Get current user ID.
     *
     * @return user ID
     * @throws IllegalStateException if context not set
     */
    public static UUID getCurrentUserId() {
        TenantContext ctx = get();
        if (ctx == null) {
            throw new IllegalStateException("TenantContext not set");
        }
        return ctx.userId();
    }
}
