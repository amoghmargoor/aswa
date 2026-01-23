package com.aswa.gateway.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * Request to create a new user.
 */
@Schema(description = "Create user request")
public record CreateUserRequest(
        @Schema(description = "Email address", example = "user@example.com")
        @NotBlank(message = "Email is required")
        @Email(message = "Invalid email format")
        String email,

        @Schema(description = "Full name", example = "John Doe")
        @NotBlank(message = "Full name is required")
        @Size(min = 2, max = 255, message = "Full name must be between 2 and 255 characters")
        String fullName,

        @Schema(description = "Password", example = "SecurePassword123!")
        @NotBlank(message = "Password is required")
        @Size(min = 8, max = 100, message = "Password must be between 8 and 100 characters")
        String password,

        @Schema(description = "User role", example = "user", allowableValues = {"admin", "user"}, defaultValue = "user")
        @Pattern(regexp = "admin|user", message = "Role must be either 'admin' or 'user'")
        String role
) {
    public CreateUserRequest {
        if (role == null || role.isBlank()) {
            role = "user";
        }
    }
}
