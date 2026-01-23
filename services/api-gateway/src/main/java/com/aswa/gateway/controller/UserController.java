package com.aswa.gateway.controller;

import com.aswa.gateway.dto.CreateUserRequest;
import com.aswa.gateway.dto.PageRequest;
import com.aswa.gateway.dto.PageResponse;
import com.aswa.gateway.dto.UpdateUserRequest;
import com.aswa.gateway.dto.UserDto;
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
 * User management controller.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
@Tag(name = "Users", description = "User management endpoints")
@SecurityRequirement(name = "Bearer Authentication")
public class UserController {

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    @Operation(summary = "List users", description = "Get paginated list of users (admin only)")
    public Mono<PageResponse<UserDto>> listUsers(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String sortBy,
            @RequestParam(defaultValue = "desc") String sortDirection) {
        log.debug("Listing users: page={}, size={}", page, size);
        PageRequest pageRequest = PageRequest.of(page, size, sortBy, sortDirection);
        // TODO: Implement service call
        return Mono.just(PageResponse.of(java.util.List.of(), 0, page, size));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get user by ID", description = "Retrieve user details")
    public Mono<UserDto> getUser(@PathVariable UUID id) {
        log.debug("Getting user: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    @Operation(summary = "Create user", description = "Create new user (admin only)")
    public Mono<UserDto> createUser(@Valid @RequestBody CreateUserRequest request) {
        log.info("Creating user: email={}", request.email());
        // TODO: Implement service call
        return Mono.empty();
    }

    @PutMapping("/{id}")
    @Operation(summary = "Update user", description = "Update existing user")
    public Mono<UserDto> updateUser(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateUserRequest request) {
        log.info("Updating user: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    @Operation(summary = "Delete user", description = "Delete user (admin only)")
    public Mono<Void> deleteUser(@PathVariable UUID id) {
        log.info("Deleting user: id={}", id);
        // TODO: Implement service call
        return Mono.empty();
    }

    @GetMapping("/me")
    @Operation(summary = "Get current user", description = "Get authenticated user details")
    public Mono<UserDto> getCurrentUser() {
        log.debug("Getting current user");
        // TODO: Implement service call
        return Mono.empty();
    }
}
