package com.aswa.gateway.controller;

import com.aswa.gateway.dto.*;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.UUID;

/**
 * Document management controller.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/documents")
@RequiredArgsConstructor
@Tag(name = "Documents", description = "Document management endpoints")
@SecurityRequirement(name = "Bearer Authentication")
public class DocumentController {

    @GetMapping
    @Operation(summary = "List documents", description = "Get paginated list of documents with optional filtering")
    public Mono<PageResponse<DocumentDto>> listDocuments(
            @RequestParam(required = false) UUID dataSourceId,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String contentType,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Listing documents: dataSourceId={}, status={}, page={}", dataSourceId, status, page);
        DocumentFilterRequest filter = new DocumentFilterRequest(dataSourceId, status, contentType);
        PageRequest pageRequest = PageRequest.of(page, size);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get document", description = "Get document details by ID")
    public Mono<DocumentDto> getDocument(@PathVariable UUID id) {
        log.debug("Getting document: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @GetMapping("/{id}/chunks")
    @Operation(summary = "Get document chunks", description = "Get all chunks for a document")
    public Flux<DocumentChunkDto> getChunks(@PathVariable UUID id) {
        log.debug("Getting chunks for document: id={}", id);
        // TODO: Implement service call
        return Flux.empty();
    }

    @GetMapping("/search")
    @Operation(summary = "Search documents", description = "Full-text search across documents")
    public Mono<PageResponse<DocumentDto>> searchDocuments(
            @RequestParam String query,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Searching documents: query='{}', page={}", query, page);
        PageRequest pageRequest = PageRequest.of(page, size);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete document", description = "Delete document and all chunks")
    public Mono<Void> deleteDocument(@PathVariable UUID id) {
        log.warn("Deleting document: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }
}
