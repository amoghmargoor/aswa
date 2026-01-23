package com.aswa.gateway.controller;

import com.aswa.gateway.dto.*;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.UUID;

/**
 * Insight management controller.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/insights")
@RequiredArgsConstructor
@Tag(name = "Insights", description = "AI-generated insight endpoints")
@SecurityRequirement(name = "Bearer Authentication")
public class InsightController {

    @GetMapping
    @Operation(summary = "List insights", description = "Get paginated list of insights with optional filtering")
    public Mono<PageResponse<InsightDto>> listInsights(
            @RequestParam(required = false) String insightType,
            @RequestParam(required = false) String severity,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String sortBy,
            @RequestParam(defaultValue = "desc") String sortDirection) {
        log.debug("Listing insights: type={}, severity={}, page={}", insightType, severity, page);
        InsightFilterRequest filter = new InsightFilterRequest(insightType, severity, category, status);
        PageRequest pageRequest = PageRequest.of(page, size, sortBy, sortDirection);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get insight", description = "Get insight details by ID")
    public Mono<InsightDto> getInsight(@PathVariable UUID id) {
        log.debug("Getting insight: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @PostMapping("/{id}/feedback")
    @Operation(summary = "Submit feedback", description = "Submit user feedback on insight accuracy")
    public Mono<InsightDto> submitFeedback(
            @PathVariable UUID id,
            @Valid @RequestBody FeedbackRequest request) {
        log.info("Submitting feedback for insight: id={}, feedback={}", id, request.feedback());
        // TODO: Implement service call
        return Mono.empty();
    }

    @GetMapping("/summary")
    @Operation(summary = "Get insights summary", description = "Get aggregated insights statistics")
    public Mono<InsightSummaryDto> getSummary() {
        log.debug("Getting insights summary");
        // TODO: Implement service call
        return Mono.empty();
    }

    @GetMapping("/search")
    @Operation(summary = "Search insights", description = "Full-text search across insights")
    public Mono<PageResponse<InsightDto>> searchInsights(
            @RequestParam String query,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Searching insights: query='{}', page={}", query, page);
        PageRequest pageRequest = PageRequest.of(page, size);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete insight", description = "Delete insight")
    public Mono<Void> deleteInsight(@PathVariable UUID id) {
        log.warn("Deleting insight: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }
}
