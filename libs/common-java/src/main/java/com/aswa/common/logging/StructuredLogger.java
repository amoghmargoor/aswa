package com.aswa.common.logging;

import java.util.HashMap;
import java.util.Map;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Structured logger that wraps SLF4J and provides type-safe field logging.
 *
 * <p>This logger automatically includes MDC context in all log messages and provides a fluent API
 * for structured logging.
 */
public final class StructuredLogger {

  private final Logger logger;

  private StructuredLogger(Logger logger) {
    this.logger = logger;
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
      logger.info(formatMessage(message, fields));
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
      logger.debug(formatMessage(message, fields));
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
      logger.warn(formatMessage(message, fields));
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
      logger.error(formatMessage(message, fields));
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
      logger.error(formatMessage(message, fields), throwable);
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
      logger.trace(formatMessage(message, fields));
    }
  }

  private String formatMessage(String message, Field[] fields) {
    if (fields.length == 0) {
      return message;
    }

    Map<String, Object> fieldMap = new HashMap<>();
    for (Field field : fields) {
      fieldMap.put(field.key(), field.value());
    }

    // Message with fields appended in JSON-like format
    // The actual JSON formatting will be done by logback-logstash-encoder
    StringBuilder sb = new StringBuilder(message);
    for (Map.Entry<String, Object> entry : fieldMap.entrySet()) {
      sb.append(" ").append(entry.getKey()).append("=").append(entry.getValue());
    }
    return sb.toString();
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
}
