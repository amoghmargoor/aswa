package com.aswa.gateway.controller;

import com.aswa.gateway.dto.ApiKeyDto;
import com.aswa.gateway.dto.CreateApiKeyRequest;
import com.aswa.gateway.dto.PageRequest;
import com.aswa.gateway.dto.PageResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.UUID;

/**
 * API key management controller.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/api-keys")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
@Tag(name = "API Keys", description = "API key management endpoints (admin only)")
@SecurityRequirement(name = "Bearer Authentication")
public class ApiKeyController {

    @GetMapping
    @Operation(summary = "List API keys", description = "Get paginated list of API keys")
    public Mono<PageResponse<ApiKeyDto>> listApiKeys(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Listing API keys: page={}, size={}", page, size);
        PageRequest pageRequest = PageRequest.of(page, size);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get API key", description = "Get API key details (key value not included)")
    public Mono<ApiKeyDto> getApiKey(@PathVariable UUID id) {
        log.debug("Getting API key: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @PostMapping
    @Operation(summary = "Create API key", description = "Create new API key (returns key only once)")
    public Mono<ApiKeyDto> createApiKey(@Valid @RequestBody CreateApiKeyRequest request) {
        log.info("Creating API key: name={}", request.name());
        // TODO: Implement service call
        return Mono.empty();
    }

    @DeleteMapping("/{id}/revoke")
    @Operation(summary = "Revoke API key", description = "Revoke/deactivate API key")
    public Mono<Void> revokeApiKey(@PathVariable UUID id) {
        log.warn("Revoking API key: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete API key", description = "Permanently delete API key")
    public Mono<Void> deleteApiKey(@PathVariable UUID id) {
        log.warn("Deleting API key: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }
}
