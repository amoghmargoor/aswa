package com.aswa.gateway.controller;

import com.aswa.gateway.dto.AlertConfigDto;
import com.aswa.gateway.dto.CreateAlertRequest;
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
 * Alert configuration controller.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/alerts")
@RequiredArgsConstructor
@Tag(name = "Alerts", description = "Alert configuration endpoints")
@SecurityRequirement(name = "Bearer Authentication")
public class AlertController {

    @GetMapping
    @Operation(summary = "List alerts", description = "Get paginated list of alert configurations")
    public Mono<PageResponse<AlertConfigDto>> listAlerts(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Listing alerts: page={}, size={}", page, size);
        PageRequest pageRequest = PageRequest.of(page, size);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get alert", description = "Get alert configuration by ID")
    public Mono<AlertConfigDto> getAlert(@PathVariable UUID id) {
        log.debug("Getting alert: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    @Operation(summary = "Create alert", description = "Create new alert configuration (admin only)")
    public Mono<AlertConfigDto> createAlert(@Valid @RequestBody CreateAlertRequest request) {
        log.info("Creating alert: name={}, type={}", request.name(), request.alertType());
        // TODO: Implement service call
        return Mono.empty();
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    @Operation(summary = "Update alert", description = "Update alert configuration (admin only)")
    public Mono<AlertConfigDto> updateAlert(
            @PathVariable UUID id,
            @Valid @RequestBody CreateAlertRequest request) {
        log.info("Updating alert: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    @Operation(summary = "Delete alert", description = "Delete alert configuration (admin only)")
    public Mono<Void> deleteAlert(@PathVariable UUID id) {
        log.warn("Deleting alert: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @GetMapping("/{id}/history")
    @Operation(summary = "Get alert history", description = "Get history of alert triggers")
    public Mono<PageResponse<Object>> getAlertHistory(
            @PathVariable UUID id,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Getting alert history: id={}, page={}", id, page);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }
}
