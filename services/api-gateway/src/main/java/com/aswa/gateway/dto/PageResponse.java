package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

/**
 * Paginated response wrapper.
 */
@Schema(description = "Paginated response")
public record PageResponse<T>(
        @Schema(description = "Page content")
        List<T> content,

        @Schema(description = "Total number of elements", example = "100")
        long totalElements,

        @Schema(description = "Total number of pages", example = "5")
        int totalPages,

        @Schema(description = "Current page number", example = "0")
        int currentPage,

        @Schema(description = "Page size", example = "20")
        int pageSize
) {
    public static <T> PageResponse<T> of(List<T> content, long totalElements, int currentPage, int pageSize) {
        int totalPages = (int) Math.ceil((double) totalElements / pageSize);
        return new PageResponse<>(content, totalElements, totalPages, currentPage, pageSize);
    }
}
