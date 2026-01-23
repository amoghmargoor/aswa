package com.aswa.gateway.exception;

import com.aswa.common.exception.AswaException;
import com.aswa.common.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.support.WebExchangeBindException;
import reactor.core.publisher.Mono;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Global exception handler for all controllers.
 *
 * Converts exceptions to consistent API responses.
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(AswaException.class)
    public Mono<ResponseEntity<ApiErrorResponse>> handleAswaException(AswaException ex) {
        log.error("AswaException: {} - {}", ex.getErrorCode(), ex.getMessage(), ex);

        HttpStatus status = mapErrorCodeToHttpStatus(ex.getErrorCode());
        ApiErrorResponse response = new ApiErrorResponse(
                ex.getErrorCode().name(),
                ex.getMessage(),
                ex.getDetails(),
                Instant.now()
        );

        return Mono.just(ResponseEntity.status(status).body(response));
    }

    @ExceptionHandler(WebExchangeBindException.class)
    public Mono<ResponseEntity<ApiErrorResponse>> handleValidationException(WebExchangeBindException ex) {
        log.warn("Validation error: {}", ex.getMessage());

        Map<String, Object> errors = new HashMap<>();
        for (FieldError error : ex.getFieldErrors()) {
            errors.put(error.getField(), error.getDefaultMessage());
        }

        ApiErrorResponse response = new ApiErrorResponse(
                "VALIDATION_ERROR",
                "Validation failed for request",
                errors,
                Instant.now()
        );

        return Mono.just(ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response));
    }

    @ExceptionHandler(AccessDeniedException.class)
    public Mono<ResponseEntity<ApiErrorResponse>> handleAccessDenied(AccessDeniedException ex) {
        log.warn("Access denied: {}", ex.getMessage());

        ApiErrorResponse response = new ApiErrorResponse(
                "ACCESS_DENIED",
                "Access denied - insufficient permissions",
                Map.of("message", ex.getMessage()),
                Instant.now()
        );

        return Mono.just(ResponseEntity.status(HttpStatus.FORBIDDEN).body(response));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public Mono<ResponseEntity<ApiErrorResponse>> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("Illegal argument: {}", ex.getMessage());

        ApiErrorResponse response = new ApiErrorResponse(
                "INVALID_ARGUMENT",
                ex.getMessage(),
                Map.of(),
                Instant.now()
        );

        return Mono.just(ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response));
    }

    @ExceptionHandler(Exception.class)
    public Mono<ResponseEntity<ApiErrorResponse>> handleGenericException(Exception ex) {
        log.error("Unexpected error", ex);

        ApiErrorResponse response = new ApiErrorResponse(
                "INTERNAL_ERROR",
                "An unexpected error occurred",
                Map.of("message", ex.getMessage()),
                Instant.now()
        );

        return Mono.just(ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response));
    }

    private HttpStatus mapErrorCodeToHttpStatus(ErrorCode errorCode) {
        return switch (errorCode) {
            case VALIDATION_ERROR, INVALID_INPUT -> HttpStatus.BAD_REQUEST;
            case AUTHENTICATION_FAILED, INVALID_CREDENTIALS -> HttpStatus.UNAUTHORIZED;
            case AUTHORIZATION_FAILED, INSUFFICIENT_PERMISSIONS -> HttpStatus.FORBIDDEN;
            case NOT_FOUND -> HttpStatus.NOT_FOUND;
            case RESOURCE_CONFLICT, DUPLICATE_RESOURCE -> HttpStatus.CONFLICT;
            case RATE_LIMIT_EXCEEDED -> HttpStatus.TOO_MANY_REQUESTS;
            default -> HttpStatus.INTERNAL_SERVER_ERROR;
        };
    }

    /**
     * Standard API error response.
     */
    public record ApiErrorResponse(
            String errorCode,
            String message,
            Map<String, Object> details,
            Instant timestamp
    ) {
    }
}
