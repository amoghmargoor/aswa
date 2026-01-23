package com.aswa.gateway.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Document chunk data transfer object.
 */
@Schema(description = "Document chunk (smaller piece for embedding)")
@JsonInclude(JsonInclude.Include.NON_NULL)
public record DocumentChunkDto(
        @Schema(description = "Chunk ID", example = "550e8400-e29b-41d4-a716-446655440000")
        UUID id,

        @Schema(description = "Document ID", example = "123e4567-e89b-12d3-a456-426614174000")
        UUID documentId,

        @Schema(description = "Chunk index (0-based)", example = "0")
        int chunkIndex,

        @Schema(description = "Chunk content")
        String content,

        @Schema(description = "Chunk metadata")
        Map<String, Object> chunkMetadata,

        @Schema(description = "Vector store ID reference", example = "vec-123")
        String vectorId,

        @Schema(description = "Created timestamp", example = "2024-01-15T10:30:00Z")
        Instant createdAt
) {
}
