package com.aswa.common.exception;

import static org.assertj.core.assertions.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;

class AswaExceptionTest {

  @Test
  void shouldCreateExceptionWithCodeAndMessage() {
    AswaException exception = new AswaException(ErrorCode.VALIDATION_ERROR, "Test message");

    assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.VALIDATION_ERROR);
    assertThat(exception.getMessage()).isEqualTo("Test message");
    assertThat(exception.getMetadata()).isEmpty();
    assertThat(exception.getRequestId()).isNull();
    assertThat(exception.getCause()).isNull();
  }

  @Test
  void shouldCreateExceptionWithCause() {
    RuntimeException cause = new RuntimeException("Original error");
    AswaException exception =
        new AswaException(ErrorCode.INTERNAL_ERROR, "Wrapper message", cause);

    assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.INTERNAL_ERROR);
    assertThat(exception.getMessage()).isEqualTo("Wrapper message");
    assertThat(exception.getCause()).isEqualTo(cause);
  }

  @Test
  void shouldCreateExceptionWithMetadata() {
    Map<String, Object> metadata = Map.of("field", "email", "value", "invalid@");
    AswaException exception =
        new AswaException(ErrorCode.VALIDATION_ERROR, "Invalid email", null, metadata, null);

    assertThat(exception.getMetadata()).containsAllEntriesOf(metadata);
  }

  @Test
  void shouldCreateExceptionWithBuilder() {
    AswaException exception =
        AswaException.builder(ErrorCode.NOT_FOUND, "Resource not found")
            .metadata("resourceId", "123")
            .metadata("resourceType", "User")
            .requestId("req-456")
            .build();

    assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.NOT_FOUND);
    assertThat(exception.getMessage()).isEqualTo("Resource not found");
    assertThat(exception.getMetadata()).containsEntry("resourceId", "123");
    assertThat(exception.getMetadata()).containsEntry("resourceType", "User");
    assertThat(exception.getRequestId()).isEqualTo("req-456");
  }

  @Test
  void shouldConvertToApiError() {
    AswaException exception =
        AswaException.builder(ErrorCode.UNAUTHORIZED, "Invalid credentials")
            .metadata("username", "testuser")
            .requestId("req-789")
            .build();

    Map<String, Object> apiError = exception.toApiError();

    assertThat(apiError).containsEntry("code", "UNAUTHORIZED");
    assertThat(apiError).containsEntry("message", "Invalid credentials");
    assertThat(apiError).containsEntry("requestId", "req-789");
    assertThat(apiError).containsKey("details");
  }

  @Test
  void shouldImmutablyReturnMetadata() {
    Map<String, Object> metadata = Map.of("key", "value");
    AswaException exception =
        new AswaException(ErrorCode.INTERNAL_ERROR, "Test", null, metadata, null);

    Map<String, Object> returnedMetadata = exception.getMetadata();
    assertThat(returnedMetadata).isNotSameAs(metadata);
    assertThat(returnedMetadata).containsAllEntriesOf(metadata);
  }
}
