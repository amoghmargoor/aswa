package com.aswa.common.model;

import com.aswa.common.exception.AswaException;
import com.aswa.common.exception.ErrorCode;
import java.time.Instant;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;

/**
 * Generic API response wrapper.
 *
 * @param <T> the type of data in the response
 * @param success whether the request was successful
 * @param data the response data (null if error)
 * @param error the error information (null if success)
 * @param timestamp the response timestamp
 * @param requestId the request ID for tracing
 */
public record ApiResponse<T>(
    boolean success,
    @Nullable T data,
    @Nullable ApiError error,
    @NonNull Instant timestamp,
    @Nullable String requestId) {

  /**
   * Creates a successful API response.
   *
   * @param <T> the type of data
   * @param data the response data
   * @return a successful ApiResponse
   */
  @NonNull
  public static <T> ApiResponse<T> success(@NonNull T data) {
    return new ApiResponse<>(true, data, null, Instant.now(), null);
  }

  /**
   * Creates a successful API response with a request ID.
   *
   * @param <T> the type of data
   * @param data the response data
   * @param requestId the request ID
   * @return a successful ApiResponse
   */
  @NonNull
  public static <T> ApiResponse<T> success(@NonNull T data, @NonNull String requestId) {
    return new ApiResponse<>(true, data, null, Instant.now(), requestId);
  }

  /**
   * Creates an error API response.
   *
   * @param <T> the type of data
   * @param error the error information
   * @return an error ApiResponse
   */
  @NonNull
  public static <T> ApiResponse<T> error(@NonNull ApiError error) {
    return new ApiResponse<>(false, null, error, Instant.now(), null);
  }

  /**
   * Creates an error API response from an error code and message.
   *
   * @param <T> the type of data
   * @param errorCode the error code
   * @param message the error message
   * @return an error ApiResponse
   */
  @NonNull
  public static <T> ApiResponse<T> error(@NonNull ErrorCode errorCode, @NonNull String message) {
    ApiError apiError = ApiError.of(errorCode.getCode(), message);
    return new ApiResponse<>(false, null, apiError, Instant.now(), null);
  }

  /**
   * Creates an error API response from an AswaException.
   *
   * @param <T> the type of data
   * @param exception the exception
   * @return an error ApiResponse
   */
  @NonNull
  public static <T> ApiResponse<T> error(@NonNull AswaException exception) {
    ApiError apiError =
        new ApiError(
            exception.getErrorCode().getCode(), exception.getMessage(), exception.getMetadata());
    return new ApiResponse<>(false, null, apiError, Instant.now(), exception.getRequestId());
  }
}
