package com.aswa.common.auth.mfa;

/**
 * MFA repository interface for storing MFA configurations.
 */
public interface MfaRepository {

    /**
     * Find MFA configuration by user and tenant.
     */
    MfaConfiguration findByUserIdAndTenantId(String userId, String tenantId);

    /**
     * Save MFA configuration.
     */
    void save(MfaConfiguration configuration);

    /**
     * Delete MFA configuration.
     */
    void deleteByUserIdAndTenantId(String userId, String tenantId);
}
