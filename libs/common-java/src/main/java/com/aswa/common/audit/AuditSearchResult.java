package com.aswa.common.audit;

import java.util.List;

/**
 * Result of an audit search.
 */
public record AuditSearchResult(
    List<AuditEvent> events,
    long totalCount,
    int offset,
    int limit
) {

    public boolean hasMore() {
        return offset + events.size() < totalCount;
    }
}
