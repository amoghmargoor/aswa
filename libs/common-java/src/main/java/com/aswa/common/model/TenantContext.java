package com.aswa.common.model;

import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.jspecify.annotations.NonNull;

/**
 * Tenant context containing tenant and user information.
 *
 * <p>This record encapsulates tenant-scoped request context including tenant ID, user ID, roles,
 * and additional metadata.
 *
 * @param tenantId the tenant ID
 * @param userId the user ID
 * @param roles the user's roles
 * @param metadata additional context metadata
 */
public record TenantContext(
    @NonNull UUID tenantId,
    @NonNull UUID userId,
    @NonNull Set<String> roles,
    @NonNull Map<String, String> metadata) {

  /**
   * Creates a new TenantContext with the specified IDs and roles.
   *
   * @param tenantId the tenant ID
   * @param userId the user ID
   * @param roles the user's roles
   * @return a new TenantContext
   */
  @NonNull
  public static TenantContext of(
      @NonNull UUID tenantId, @NonNull UUID userId, @NonNull Set<String> roles) {
    return new TenantContext(tenantId, userId, roles, Map.of());
  }

  /**
   * Checks if the user has the specified role.
   *
   * @param role the role to check
   * @return true if the user has the role
   */
  public boolean hasRole(@NonNull String role) {
    return roles.contains(role);
  }

  /**
   * Checks if the user has the admin role.
   *
   * @return true if the user is an admin
   */
  public boolean isAdmin() {
    return hasRole("admin") || hasRole("ADMIN");
  }
}
