package com.aswa.common.exception;

import java.util.HashMap;
import java.util.Map;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;

/**
 * Base exception class for all ASWA exceptions.
 *
 * <p>This exception supports structured error information including error codes, metadata, and
 * request IDs for tracing.
 */
public class AswaException extends RuntimeException {
  private final ErrorCode errorCode;
  private final Map<String, Object> metadata;
  private final String requestId;

  /**
   * Creates a new AswaException with the specified error code and message.
   *
   * @param errorCode the error code
   * @param message the error message
   */
  public AswaException(@NonNull ErrorCode errorCode, @NonNull String message) {
    this(errorCode, message, null, null, null);
  }

  /**
   * Creates a new AswaException with the specified error code, message, and cause.
   *
   * @param errorCode the error code
   * @param message the error message
   * @param cause the underlying cause
   */
  public AswaException(
      @NonNull ErrorCode errorCode, @NonNull String message, @Nullable Throwable cause) {
    this(errorCode, message, cause, null, null);
  }

  /**
   * Creates a new AswaException with all parameters.
   *
   * @param errorCode the error code
   * @param message the error message
   * @param cause the underlying cause
   * @param metadata additional metadata
   * @param requestId the request ID for tracing
   */
  public AswaException(
      @NonNull ErrorCode errorCode,
      @NonNull String message,
      @Nullable Throwable cause,
      @Nullable Map<String, Object> metadata,
      @Nullable String requestId) {
    super(message, cause);
    this.errorCode = errorCode;
    this.metadata = metadata != null ? new HashMap<>(metadata) : new HashMap<>();
    this.requestId = requestId;
  }

  /**
   * Gets the error code.
   *
   * @return the error code
   */
  @NonNull
  public ErrorCode getErrorCode() {
    return errorCode;
  }

  /**
   * Gets the metadata map.
   *
   * @return the metadata
   */
  @NonNull
  public Map<String, Object> getMetadata() {
    return new HashMap<>(metadata);
  }

  /**
   * Gets the request ID.
   *
   * @return the request ID, or null if not set
   */
  @Nullable
  public String getRequestId() {
    return requestId;
  }

  /**
   * Converts this exception to an API error response map.
   *
   * @return API error map
   */
  @NonNull
  public Map<String, Object> toApiError() {
    Map<String, Object> error = new HashMap<>();
    error.put("code", errorCode.getCode());
    error.put("message", getMessage());
    error.put("details", metadata);
    if (requestId != null) {
      error.put("requestId", requestId);
    }
    return error;
  }

  /**
   * Creates a builder for constructing AswaException instances.
   *
   * @param errorCode the error code
   * @param message the error message
   * @return a new builder
   */
  @NonNull
  public static Builder builder(@NonNull ErrorCode errorCode, @NonNull String message) {
    return new Builder(errorCode, message);
  }

  /** Builder for AswaException. */
  public static class Builder {
    private final ErrorCode errorCode;
    private final String message;
    private Throwable cause;
    private Map<String, Object> metadata = new HashMap<>();
    private String requestId;

    private Builder(ErrorCode errorCode, String message) {
      this.errorCode = errorCode;
      this.message = message;
    }

    /**
     * Sets the cause.
     *
     * @param cause the underlying cause
     * @return this builder
     */
    @NonNull
    public Builder cause(@Nullable Throwable cause) {
      this.cause = cause;
      return this;
    }

    /**
     * Adds a metadata entry.
     *
     * @param key the metadata key
     * @param value the metadata value
     * @return this builder
     */
    @NonNull
    public Builder metadata(@NonNull String key, @NonNull Object value) {
      this.metadata.put(key, value);
      return this;
    }

    /**
     * Sets all metadata.
     *
     * @param metadata the metadata map
     * @return this builder
     */
    @NonNull
    public Builder metadata(@NonNull Map<String, Object> metadata) {
      this.metadata = new HashMap<>(metadata);
      return this;
    }

    /**
     * Sets the request ID.
     *
     * @param requestId the request ID
     * @return this builder
     */
    @NonNull
    public Builder requestId(@NonNull String requestId) {
      this.requestId = requestId;
      return this;
    }

    /**
     * Builds the AswaException.
     *
     * @return the exception
     */
    @NonNull
    public AswaException build() {
      return new AswaException(errorCode, message, cause, metadata, requestId);
    }
  }
}
