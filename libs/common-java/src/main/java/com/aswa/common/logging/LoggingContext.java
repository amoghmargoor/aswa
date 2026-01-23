package com.aswa.common.logging;

import java.util.UUID;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;
import org.slf4j.MDC;

/**
 * Logging context for structured logging with MDC (Mapped Diagnostic Context).
 *
 * <p>This class provides static methods to set and clear context variables that will be
 * automatically included in all log messages.
 */
public final class LoggingContext {

  /** MDC key for request ID. */
  public static final String REQUEST_ID = "requestId";

  /** MDC key for tenant ID. */
  public static final String TENANT_ID = "tenantId";

  /** MDC key for user ID. */
  public static final String USER_ID = "userId";

  /** MDC key for trace ID. */
  public static final String TRACE_ID = "traceId";

  private LoggingContext() {
    // Utility class
  }

  /**
   * Sets the request ID in the logging context.
   *
   * @param requestId the request ID
   */
  public static void setRequestId(@NonNull String requestId) {
    MDC.put(REQUEST_ID, requestId);
  }

  /**
   * Sets the tenant ID in the logging context.
   *
   * @param tenantId the tenant ID
   */
  public static void setTenantId(@NonNull UUID tenantId) {
    MDC.put(TENANT_ID, tenantId.toString());
  }

  /**
   * Sets the user ID in the logging context.
   *
   * @param userId the user ID
   */
  public static void setUserId(@NonNull UUID userId) {
    MDC.put(USER_ID, userId.toString());
  }

  /**
   * Sets the trace ID in the logging context.
   *
   * @param traceId the trace ID
   */
  public static void setTraceId(@NonNull String traceId) {
    MDC.put(TRACE_ID, traceId);
  }

  /**
   * Gets the request ID from the logging context.
   *
   * @return the request ID, or null if not set
   */
  @Nullable
  public static String getRequestId() {
    return MDC.get(REQUEST_ID);
  }

  /**
   * Gets the tenant ID from the logging context.
   *
   * @return the tenant ID, or null if not set
   */
  @Nullable
  public static String getTenantId() {
    return MDC.get(TENANT_ID);
  }

  /**
   * Gets the user ID from the logging context.
   *
   * @return the user ID, or null if not set
   */
  @Nullable
  public static String getUserId() {
    return MDC.get(USER_ID);
  }

  /**
   * Gets the trace ID from the logging context.
   *
   * @return the trace ID, or null if not set
   */
  @Nullable
  public static String getTraceId() {
    return MDC.get(TRACE_ID);
  }

  /**
   * Clears all context variables from MDC.
   *
   * <p>This should be called at the end of request processing to prevent context leakage.
   */
  public static void clear() {
    MDC.clear();
  }
}
