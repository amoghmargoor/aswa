package com.aswa.common.util;

import com.aswa.common.exception.AswaException;
import com.aswa.common.exception.ErrorCode;
import java.util.UUID;
import java.util.regex.Pattern;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;

/**
 * Input validation utilities.
 *
 * <p>Provides methods to validate common input types and throw AswaException on validation
 * failures.
 */
public final class ValidationUtils {

  private static final Pattern EMAIL_PATTERN =
      Pattern.compile("^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$");

  private static final Pattern UUID_PATTERN =
      Pattern.compile("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$");

  private ValidationUtils() {
    // Utility class
  }

  /**
   * Validates that a string is not null or blank.
   *
   * @param value the value to validate
   * @param fieldName the field name for error messages
   * @return the validated value
   * @throws AswaException if validation fails
   */
  @NonNull
  public static String requireNotBlank(@Nullable String value, @NonNull String fieldName) {
    if (value == null || value.isBlank()) {
      throw AswaException.builder(
              ErrorCode.VALIDATION_ERROR, fieldName + " must not be blank or null")
          .metadata("fieldName", fieldName)
          .build();
    }
    return value;
  }

  /**
   * Validates that an object is not null.
   *
   * @param <T> the object type
   * @param value the value to validate
   * @param fieldName the field name for error messages
   * @return the validated value
   * @throws AswaException if validation fails
   */
  @NonNull
  public static <T> T requireNotNull(@Nullable T value, @NonNull String fieldName) {
    if (value == null) {
      throw AswaException.builder(ErrorCode.VALIDATION_ERROR, fieldName + " must not be null")
          .metadata("fieldName", fieldName)
          .build();
    }
    return value;
  }

  /**
   * Validates that a string is a valid email address.
   *
   * @param email the email to validate
   * @return the validated email
   * @throws AswaException if validation fails
   */
  @NonNull
  public static String requireValidEmail(@Nullable String email) {
    requireNotBlank(email, "email");
    if (!EMAIL_PATTERN.matcher(email).matches()) {
      throw AswaException.builder(ErrorCode.VALIDATION_ERROR, "Invalid email address format")
          .metadata("email", email)
          .build();
    }
    return email;
  }

  /**
   * Validates that a string is a valid UUID.
   *
   * @param uuidString the UUID string to validate
   * @return the validated UUID
   * @throws AswaException if validation fails
   */
  @NonNull
  public static UUID requireValidUuid(@Nullable String uuidString) {
    requireNotBlank(uuidString, "uuid");
    if (!UUID_PATTERN.matcher(uuidString).matches()) {
      throw AswaException.builder(ErrorCode.VALIDATION_ERROR, "Invalid UUID format")
          .metadata("uuid", uuidString)
          .build();
    }
    try {
      return UUID.fromString(uuidString);
    } catch (IllegalArgumentException e) {
      throw AswaException.builder(ErrorCode.VALIDATION_ERROR, "Invalid UUID format")
          .cause(e)
          .metadata("uuid", uuidString)
          .build();
    }
  }

  /**
   * Validates that a number is within a specified range.
   *
   * @param value the value to validate
   * @param min the minimum value (inclusive)
   * @param max the maximum value (inclusive)
   * @param fieldName the field name for error messages
   * @return the validated value
   * @throws AswaException if validation fails
   */
  public static int requireInRange(int value, int min, int max, @NonNull String fieldName) {
    if (value < min || value > max) {
      throw AswaException.builder(
              ErrorCode.VALIDATION_ERROR,
              fieldName + " must be between " + min + " and " + max)
          .metadata("fieldName", fieldName)
          .metadata("value", value)
          .metadata("min", min)
          .metadata("max", max)
          .build();
    }
    return value;
  }

  /**
   * Validates that a string matches a pattern.
   *
   * @param value the value to validate
   * @param pattern the pattern to match
   * @param fieldName the field name for error messages
   * @return the validated value
   * @throws AswaException if validation fails
   */
  @NonNull
  public static String requirePattern(
      @Nullable String value, @NonNull Pattern pattern, @NonNull String fieldName) {
    requireNotBlank(value, fieldName);
    if (!pattern.matcher(value).matches()) {
      throw AswaException.builder(
              ErrorCode.VALIDATION_ERROR, fieldName + " does not match required pattern")
          .metadata("fieldName", fieldName)
          .metadata("value", value)
          .metadata("pattern", pattern.pattern())
          .build();
    }
    return value;
  }
}
