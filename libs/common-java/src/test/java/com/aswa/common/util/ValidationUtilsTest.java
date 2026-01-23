package com.aswa.common.util;

import static org.assertj.core.assertions.Assertions.assertThat;
import static org.assertj.core.assertions.Assertions.assertThatThrownBy;

import com.aswa.common.exception.AswaException;
import com.aswa.common.exception.ErrorCode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

class ValidationUtilsTest {

  @Test
  void shouldValidateNotBlank() {
    String result = ValidationUtils.requireNotBlank("test", "fieldName");
    assertThat(result).isEqualTo("test");
  }

  @ParameterizedTest
  @NullAndEmptySource
  @ValueSource(strings = {" ", "  ", "\t", "\n"})
  void shouldThrowOnBlankString(String value) {
    assertThatThrownBy(() -> ValidationUtils.requireNotBlank(value, "fieldName"))
        .isInstanceOf(AswaException.class)
        .hasMessageContaining("must not be blank")
        .extracting("errorCode")
        .isEqualTo(ErrorCode.VALIDATION_ERROR);
  }

  @Test
  void shouldValidateNotNull() {
    String result = ValidationUtils.requireNotNull("test", "fieldName");
    assertThat(result).isEqualTo("test");
  }

  @Test
  void shouldThrowOnNull() {
    assertThatThrownBy(() -> ValidationUtils.requireNotNull(null, "fieldName"))
        .isInstanceOf(AswaException.class)
        .hasMessageContaining("must not be null")
        .extracting("errorCode")
        .isEqualTo(ErrorCode.VALIDATION_ERROR);
  }

  @ParameterizedTest
  @ValueSource(
      strings = {
        "test@example.com",
        "user.name@example.com",
        "user+tag@example.co.uk",
        "test_user@sub.example.com"
      })
  void shouldValidateValidEmail(String email) {
    String result = ValidationUtils.requireValidEmail(email);
    assertThat(result).isEqualTo(email);
  }

  @ParameterizedTest
  @ValueSource(strings = {"invalid", "@example.com", "test@", "test@.com", "test @example.com"})
  void shouldThrowOnInvalidEmail(String email) {
    assertThatThrownBy(() -> ValidationUtils.requireValidEmail(email))
        .isInstanceOf(AswaException.class)
        .hasMessageContaining("Invalid email")
        .extracting("errorCode")
        .isEqualTo(ErrorCode.VALIDATION_ERROR);
  }

  @Test
  void shouldValidateValidUuid() {
    String uuidString = "123e4567-e89b-12d3-a456-426614174000";
    UUID result = ValidationUtils.requireValidUuid(uuidString);
    assertThat(result.toString()).isEqualTo(uuidString);
  }

  @ParameterizedTest
  @ValueSource(
      strings = {
        "invalid-uuid",
        "123e4567-e89b-12d3-a456",
        "123e4567-e89b-12d3-a456-42661417400",
        "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      })
  void shouldThrowOnInvalidUuid(String uuid) {
    assertThatThrownBy(() -> ValidationUtils.requireValidUuid(uuid))
        .isInstanceOf(AswaException.class)
        .hasMessageContaining("Invalid UUID")
        .extracting("errorCode")
        .isEqualTo(ErrorCode.VALIDATION_ERROR);
  }

  @Test
  void shouldValidateInRange() {
    int result = ValidationUtils.requireInRange(5, 1, 10, "value");
    assertThat(result).isEqualTo(5);
  }

  @ParameterizedTest
  @ValueSource(ints = {0, 11, -1, 100})
  void shouldThrowOnOutOfRange(int value) {
    assertThatThrownBy(() -> ValidationUtils.requireInRange(value, 1, 10, "value"))
        .isInstanceOf(AswaException.class)
        .hasMessageContaining("must be between")
        .extracting("errorCode")
        .isEqualTo(ErrorCode.VALIDATION_ERROR);
  }
}
