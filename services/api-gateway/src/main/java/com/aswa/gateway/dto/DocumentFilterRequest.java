package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.UUID;

/**
 * Document filter request for querying documents.
 */
@Schema(description = "Document filter criteria")
public record DocumentFilterRequest(
        @Schema(description = "Data source ID", example = "123e4567-e89b-12d3-a456-426614174000")
        UUID dataSourceId,

        @Schema(description = "Processing status", example = "completed")
        String status,

        @Schema(description = "Content type", example = "text/plain")
        String contentType
) {
}
