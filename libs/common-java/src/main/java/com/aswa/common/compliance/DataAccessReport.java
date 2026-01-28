package com.aswa.common.compliance;

import java.time.Instant;
import java.util.List;

/**
 * GDPR Article 15 Data Access Report.
 */
public record DataAccessReport(
    String id,
    String tenantId,
    String userId,
    Instant generatedAt,
    String requestedBy,
    List<DataCategory> dataCategories,
    List<ProcessingActivity> processingActivities,
    List<DataSharingRecord> dataSharingRecords,
    List<RetentionPolicy> retentionPolicies,
    List<String> userRights
) {

    public record DataCategory(
        String name,
        String description,
        List<String> sources,
        String purpose
    ) {}

    public record ProcessingActivity(
        String activity,
        Instant timestamp,
        String details
    ) {}

    public record DataSharingRecord(
        String recipient,
        String purpose,
        Instant sharedAt
    ) {}

    public record RetentionPolicy(
        String dataType,
        int retentionDays,
        String unit
    ) {}
}
