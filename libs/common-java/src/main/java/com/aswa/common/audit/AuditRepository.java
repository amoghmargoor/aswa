package com.aswa.common.audit;

import java.util.concurrent.CompletableFuture;

/**
 * Repository interface for audit events.
 */
public interface AuditRepository {

    /**
     * Save an audit event.
     */
    void save(AuditEvent event);

    /**
     * Search audit events.
     */
    CompletableFuture<AuditSearchResult> search(AuditSearchCriteria criteria);
}
