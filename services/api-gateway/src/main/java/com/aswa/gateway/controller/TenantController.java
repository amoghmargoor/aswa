package com.aswa.gateway.controller;

import com.aswa.gateway.dto.CreateTenantRequest;
import com.aswa.gateway.dto.PageRequest;
import com.aswa.gateway.dto.PageResponse;
import com.aswa.gateway.dto.TenantDto;
import com.aswa.gateway.dto.UpdateTenantRequest;
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
 * Tenant management controller (super admin only).
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/tenants")
@RequiredArgsConstructor
@PreAuthorize("hasRole('SUPER_ADMIN')")
@Tag(name = "Tenants", description = "Tenant management endpoints (super admin only)")
@SecurityRequirement(name = "Bearer Authentication")
public class TenantController {

    @GetMapping
    @Operation(summary = "List tenants", description = "Get paginated list of tenants")
    public Mono<PageResponse<TenantDto>> listTenants(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Listing tenants: page={}, size={}", page, size);
        PageRequest pageRequest = PageRequest.of(page, size);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get tenant by ID", description = "Retrieve tenant details")
    public Mono<TenantDto> getTenant(@PathVariable UUID id) {
        log.debug("Getting tenant: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @PostMapping
    @Operation(summary = "Create tenant", description = "Create new tenant")
    public Mono<TenantDto> createTenant(@Valid @RequestBody CreateTenantRequest request) {
        log.info("Creating tenant: name={}, slug={}", request.name(), request.slug());
        // TODO: Implement service call
        return Mono.empty();
    }

    @PutMapping("/{id}")
    @Operation(summary = "Update tenant", description = "Update existing tenant")
    public Mono<TenantDto> updateTenant(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateTenantRequest request) {
        log.info("Updating tenant: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete tenant", description = "Delete tenant and all associated data")
    public Mono<Void> deleteTenant(@PathVariable UUID id) {
        log.warn("Deleting tenant: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }
}
