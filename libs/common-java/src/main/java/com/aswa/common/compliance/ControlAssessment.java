package com.aswa.common.compliance;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Assessment of a single compliance control.
 */
public record ControlAssessment(
    String controlId,
    String controlName,
    String description,
    ControlStatus status,
    double score,
    List<String> evidence,
    List<String> findings,
    List<String> recommendations,
    Instant assessedAt,
    Map<String, Object> metadata
) {

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String controlId;
        private String controlName;
        private String description;
        private ControlStatus status = ControlStatus.NOT_ASSESSED;
        private double score;
        private List<String> evidence = List.of();
        private List<String> findings = List.of();
        private List<String> recommendations = List.of();
        private Instant assessedAt = Instant.now();
        private Map<String, Object> metadata = Map.of();

        public Builder controlId(String controlId) { this.controlId = controlId; return this; }
        public Builder controlName(String controlName) { this.controlName = controlName; return this; }
        public Builder description(String description) { this.description = description; return this; }
        public Builder status(ControlStatus status) { this.status = status; return this; }
        public Builder score(double score) { this.score = score; return this; }
        public Builder evidence(List<String> evidence) { this.evidence = evidence; return this; }
        public Builder findings(List<String> findings) { this.findings = findings; return this; }
        public Builder recommendations(List<String> recommendations) { this.recommendations = recommendations; return this; }
        public Builder assessedAt(Instant assessedAt) { this.assessedAt = assessedAt; return this; }
        public Builder metadata(Map<String, Object> metadata) { this.metadata = metadata; return this; }

        public ControlAssessment build() {
            return new ControlAssessment(controlId, controlName, description, status, score,
                evidence, findings, recommendations, assessedAt, metadata);
        }
    }
}
