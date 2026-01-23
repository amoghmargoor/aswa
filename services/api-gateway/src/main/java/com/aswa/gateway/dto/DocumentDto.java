package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Document data transfer object.
 */
@Schema(description = "Document information")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record DocumentDto(
        @Schema(description = "Document ID", example = "550e8400-e29b-41d4-a716-446655440000")
        UUID id,

        @Schema(description = "Data source ID", example = "123e4567-e89b-12d3-a456-426614174000")
        UUID dataSourceId,

        @Schema(description = "External ID from source system", example = "CONF-123")
        String externalId,

        @Schema(description = "Document title", example = "Q4 Strategy Document")
        String title,

        @Schema(description = "Document content")
        String content,

        @Schema(description = "Content type", example = "text/plain")
        String contentType,

        @Schema(description = "Content hash (SHA-256)", example = "abc123...")
        String contentHash,

        @Schema(description = "Document metadata")
        Map<String, Object> metadata,

        @Schema(description = "File size in bytes", example = "102400")
        Long fileSize,

        @Schema(description = "Processing status", example = "completed")
        String processedStatus,

        @Schema(description = "Error message if processing failed")
        String errorMessage,

        @Schema(description = "Processed timestamp", example = "2024-01-15T10:30:00Z")
        Instant processedAt,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt
) {
}
