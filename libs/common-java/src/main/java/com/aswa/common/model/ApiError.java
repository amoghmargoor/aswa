package com.aswa.common.model;

import java.util.Map;
import org.jspecify.annotations.NonNull;

/**
 * API error response.
 *
 * @param code the error code
 * @param message the error message
 * @param details additional error details
 */
public record ApiError(
    @NonNull String code, @NonNull String message, @NonNull Map<String, Object> details) {

  /**
   * Creates a new ApiError with the specified code and message.
   *
   * @param code the error code
   * @param message the error message
   * @return a new ApiError
   */
  @NonNull
  public static ApiError of(@NonNull String code, @NonNull String message) {
    return new ApiError(code, message, Map.of());
  }
}
