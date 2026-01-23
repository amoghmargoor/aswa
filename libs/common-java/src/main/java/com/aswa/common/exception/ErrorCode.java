package com.aswa.common.exception;

import java.util.Map;
import org.jspecify.annotations.NonNull;

/**
 * Error codes for ASWA exceptions.
 *
 * <p>Each error code is associated with an HTTP status code for API responses.
 */
public enum ErrorCode {
  VALIDATION_ERROR(400, "VALIDATION_ERROR"),
  NOT_FOUND(404, "NOT_FOUND"),
  UNAUTHORIZED(401, "UNAUTHORIZED"),
  FORBIDDEN(403, "FORBIDDEN"),
  CONFLICT(409, "CONFLICT"),
  RATE_LIMITED(429, "RATE_LIMITED"),
  EXTERNAL_SERVICE_ERROR(502, "EXTERNAL_SERVICE_ERROR"),
  INTERNAL_ERROR(500, "INTERNAL_ERROR");

  private final int httpStatus;
  private final String code;

  ErrorCode(int httpStatus, String code) {
    this.httpStatus = httpStatus;
    this.code = code;
  }

  /**
   * Get the HTTP status code associated with this error.
   *
   * @return HTTP status code
   */
  public int getHttpStatus() {
    return httpStatus;
  }

  /**
   * Get the error code string.
   *
   * @return error code
   */
  public String getCode() {
    return code;
  }

  /**
   * Convert this error code to an API error response map.
   *
   * @param message error message
   * @param details additional error details
   * @return API error map
   */
  @NonNull
  public Map<String, Object> toApiError(@NonNull String message, Map<String, Object> details) {
    return Map.of(
        "code", code,
        "message", message,
        "details", details != null ? details : Map.of());
  }
}
