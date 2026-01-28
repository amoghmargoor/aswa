package com.aswa.common.logging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Structured JSON logger for ASWA services.
 *
 * <p>This logger automatically includes MDC context in all log messages and provides a fluent API
 * for structured logging with JSON output.
 */
public final class StructuredLogger {

  private final Logger logger;
  private final ObjectMapper objectMapper;
  private final String serviceName;

  private StructuredLogger(Logger logger) {
    this.logger = logger;
    this.objectMapper = new ObjectMapper();
    this.serviceName = System.getenv().getOrDefault("SERVICE_NAME", "unknown");
  }

  /**
   * Gets a structured logger for the specified class.
   *
   * @param clazz the class
   * @return a structured logger
   */
  @NonNull
  public static StructuredLogger getLogger(@NonNull Class<?> clazz) {
    return new StructuredLogger(LoggerFactory.getLogger(clazz));
  }

  /**
   * Gets a structured logger for the specified name.
   *
   * @param name the logger name
   * @return a structured logger
   */
  @NonNull
  public static StructuredLogger getLogger(@NonNull String name) {
    return new StructuredLogger(LoggerFactory.getLogger(name));
  }

  /**
   * Logs an info message with structured fields.
   *
   * @param message the message
   * @param fields additional fields
   */
  public void info(@NonNull String message, @NonNull Field... fields) {
    if (logger.isInfoEnabled()) {
      log("INFO", message, null, fields);
    }
  }

  /**
   * Logs a debug message with structured fields.
   *
   * @param message the message
   * @param fields additional fields
   */
  public void debug(@NonNull String message, @NonNull Field... fields) {
    if (logger.isDebugEnabled()) {
      log("DEBUG", message, null, fields);
    }
  }

  /**
   * Logs a warn message with structured fields.
   *
   * @param message the message
   * @param fields additional fields
   */
  public void warn(@NonNull String message, @NonNull Field... fields) {
    if (logger.isWarnEnabled()) {
      log("WARN", message, null, fields);
    }
  }

  /**
   * Logs an error message with structured fields.
   *
   * @param message the message
   * @param fields additional fields
   */
  public void error(@NonNull String message, @NonNull Field... fields) {
    if (logger.isErrorEnabled()) {
      log("ERROR", message, null, fields);
    }
  }

  /**
   * Logs an error message with throwable and structured fields.
   *
   * @param message the message
   * @param throwable the throwable
   * @param fields additional fields
   */
  public void error(
      @NonNull String message, @NonNull Throwable throwable, @NonNull Field... fields) {
    if (logger.isErrorEnabled()) {
      log("ERROR", message, throwable, fields);
    }
  }

  /**
   * Logs a trace message with structured fields.
   *
   * @param message the message
   * @param fields additional fields
   */
  public void trace(@NonNull String message, @NonNull Field... fields) {
    if (logger.isTraceEnabled()) {
      log("TRACE", message, null, fields);
    }
  }

  private void log(String level, String message, Throwable throwable, Field[] fields) {
    Map<String, Object> logEntry = new HashMap<>();

    // Base fields
    logEntry.put("timestamp", Instant.now().toString());
    logEntry.put("level", level);
    logEntry.put("message", message);
    logEntry.put("service", serviceName);
    logEntry.put("environment", System.getenv().getOrDefault("ENVIRONMENT", "development"));
    logEntry.put("version", System.getenv().getOrDefault("VERSION", "unknown"));

    // MDC context
    String requestId = MDC.get("requestId");
    if (requestId != null) {
      logEntry.put("request_id", requestId);
    }

    String tenantId = MDC.get("tenantId");
    if (tenantId != null) {
      logEntry.put("tenant_id", tenantId);
    }

    String userId = MDC.get("userId");
    if (userId != null) {
      logEntry.put("user_id", userId);
    }

    String traceId = MDC.get("traceId");
    if (traceId != null) {
      logEntry.put("trace_id", traceId);
      logEntry.put("span_id", MDC.get("spanId"));
    }

    // Add custom fields
    for (Field field : fields) {
      logEntry.put(field.key(), field.value());
    }

    // Exception handling
    if (throwable != null) {
      Map<String, Object> exceptionInfo = new HashMap<>();
      exceptionInfo.put("type", throwable.getClass().getName());
      exceptionInfo.put("message", throwable.getMessage());

      StringBuilder stackTrace = new StringBuilder();
      for (StackTraceElement element : throwable.getStackTrace()) {
        stackTrace.append(element.toString()).append("\n");
      }
      exceptionInfo.put("stacktrace", stackTrace.toString());

      logEntry.put("exception", exceptionInfo);
    }

    try {
      String json = objectMapper.writeValueAsString(logEntry);
      switch (level) {
        case "ERROR" -> logger.error(json);
        case "WARN" -> logger.warn(json);
        case "DEBUG" -> logger.debug(json);
        case "TRACE" -> logger.trace(json);
        default -> logger.info(json);
      }
    } catch (JsonProcessingException e) {
      logger.error("Failed to serialize log entry: {}", e.getMessage());
    }
  }

  /**
   * Create a child logger with additional context.
   *
   * @param key the context key
   * @param value the context value
   * @return a context builder
   */
  public ContextBuilder with(String key, Object value) {
    return new ContextBuilder(this).with(key, value);
  }

  /**
   * Structured logging field.
   *
   * @param key the field key
   * @param value the field value
   */
  public record Field(@NonNull String key, @Nullable Object value) {

    /**
     * Creates a new field.
     *
     * @param key the field key
     * @param value the field value
     * @return a new Field
     */
    @NonNull
    public static Field of(@NonNull String key, @Nullable Object value) {
      return new Field(key, value);
    }
  }

  /**
   * Builder for adding temporary context to log messages.
   */
  public static class ContextBuilder {
    private final StructuredLogger logger;
    private final Map<String, Object> context = new HashMap<>();

    ContextBuilder(StructuredLogger logger) {
      this.logger = logger;
    }

    /**
     * Adds a context value.
     *
     * @param key the context key
     * @param value the context value
     * @return this builder
     */
    public ContextBuilder with(String key, Object value) {
      context.put(key, value);
      return this;
    }

    /**
     * Logs an info message with the accumulated context.
     *
     * @param message the message
     */
    public void info(String message) {
      logWithContext("INFO", message, null);
    }

    /**
     * Logs an error message with the accumulated context.
     *
     * @param message the message
     * @param throwable the throwable
     */
    public void error(String message, Throwable throwable) {
      logWithContext("ERROR", message, throwable);
    }

    private void logWithContext(String level, String message, Throwable throwable) {
      for (Map.Entry<String, Object> entry : context.entrySet()) {
        MDC.put(entry.getKey(), String.valueOf(entry.getValue()));
      }
      try {
        if (throwable != null) {
          logger.error(message, throwable);
        } else {
          logger.info(message);
        }
      } finally {
        for (String key : context.keySet()) {
          MDC.remove(key);
        }
      }
    }
  }
}
