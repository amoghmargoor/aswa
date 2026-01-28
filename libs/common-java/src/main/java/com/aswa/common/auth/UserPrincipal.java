package com.aswa.common.auth;

import java.util.List;
import java.util.Objects;

/**
 * Authenticated user principal.
 */
public class UserPrincipal {

    private final String id;
    private final String tenantId;
    private final String email;
    private final String name;
    private final String role;
    private final List<String> permissions;

    public UserPrincipal(
            String id,
            String tenantId,
            String email,
            String name,
            String role,
            List<String> permissions) {
        this.id = Objects.requireNonNull(id);
        this.tenantId = Objects.requireNonNull(tenantId);
        this.email = Objects.requireNonNull(email);
        this.name = name;
        this.role = Objects.requireNonNull(role);
        this.permissions = permissions != null ? permissions : List.of();
    }

    public String getId() { return id; }
    public String getTenantId() { return tenantId; }
    public String getEmail() { return email; }
    public String getName() { return name; }
    public String getRole() { return role; }
    public List<String> getPermissions() { return permissions; }

    public boolean hasPermission(String permission) {
        return permissions.contains(permission) || permissions.contains("*");
    }

    public boolean hasAnyPermission(String... requiredPermissions) {
        for (String required : requiredPermissions) {
            if (hasPermission(required)) {
                return true;
            }
        }
        return false;
    }

    public boolean hasAllPermissions(String... requiredPermissions) {
        for (String required : requiredPermissions) {
            if (!hasPermission(required)) {
                return false;
            }
        }
        return true;
    }

    public boolean isAdmin() {
        return "admin".equals(role);
    }

    @Override
    public String toString() {
        return "UserPrincipal{" +
            "id='" + id + '\'' +
            ", tenantId='" + tenantId + '\'' +
            ", email='" + email + '\'' +
            ", role='" + role + '\'' +
            '}';
    }
}
