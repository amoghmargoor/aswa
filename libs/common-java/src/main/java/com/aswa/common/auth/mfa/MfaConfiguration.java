package com.aswa.common.auth.mfa;

import java.time.Instant;
import java.util.List;

/**
 * User's MFA configuration.
 */
public record MfaConfiguration(
    String userId,
    String tenantId,
    boolean enabled,
    MfaMethod preferredMethod,
    List<MfaMethodConfig> methods,
    Instant createdAt,
    Instant updatedAt
) {

    public boolean hasMethod(MfaMethod method) {
        return methods.stream().anyMatch(m -> m.method() == method && m.verified());
    }

    public MfaMethodConfig getMethodConfig(MfaMethod method) {
        return methods.stream()
            .filter(m -> m.method() == method)
            .findFirst()
            .orElse(null);
    }
}
