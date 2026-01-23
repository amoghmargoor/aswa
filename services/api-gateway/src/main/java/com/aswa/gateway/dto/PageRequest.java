package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

/**
 * Pagination request parameters.
 */
@Schema(description = "Pagination request parameters")
public record PageRequest(
        @Schema(description = "Page number (0-based)", example = "0", defaultValue = "0")
        @Min(0)
        int page,

        @Schema(description = "Page size", example = "20", defaultValue = "20")
        @Min(1)
        @Max(100)
        int size,

        @Schema(description = "Sort field", example = "created_at")
        String sortBy,

        @Schema(description = "Sort direction", example = "desc", allowableValues = {"asc", "desc"})
        String sortDirection
) {
    public PageRequest {
        if (page < 0) page = 0;
        if (size < 1) size = 20;
        if (size > 100) size = 100;
        if (sortDirection == null || (!sortDirection.equals("asc") && !sortDirection.equals("desc"))) {
            sortDirection = "desc";
        }
    }

    public static PageRequest of(int page, int size) {
        return new PageRequest(page, size, null, "desc");
    }

    public static PageRequest of(int page, int size, String sortBy, String sortDirection) {
        return new PageRequest(page, size, sortBy, sortDirection);
    }
}
