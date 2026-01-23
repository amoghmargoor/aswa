package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * Request to update an existing user.
 */
@Schema(description = "Update user request")
public record UpdateUserRequest(
        @Schema(description = "Email address", example = "user@example.com")
        @Email(message = "Invalid email format")
        String email,

        @Schema(description = "Full name", example = "John Doe")
        @Size(min = 2, max = 255, message = "Full name must be between 2 and 255 characters")
        String fullName,

        @Schema(description = "User role", example = "admin", allowableValues = {"admin", "user"})
        @Pattern(regexp = "admin|user", message = "Role must be either 'admin' or 'user'")
        String role,

        @Schema(description = "Account status", example = "active", allowableValues = {"active", "suspended", "inactive"})
        @Pattern(regexp = "active|suspended|inactive", message = "Status must be 'active', 'suspended', or 'inactive'")
        String status
) {
}
