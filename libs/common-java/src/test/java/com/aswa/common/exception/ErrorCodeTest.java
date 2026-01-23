package com.aswa.common.exception;

import static org.assertj.core.assertions.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ErrorCodeTest {

  @Test
  void shouldHaveCorrectHttpStatus() {
    assertThat(ErrorCode.VALIDATION_ERROR.getHttpStatus()).isEqualTo(400);
    assertThat(ErrorCode.UNAUTHORIZED.getHttpStatus()).isEqualTo(401);
    assertThat(ErrorCode.FORBIDDEN.getHttpStatus()).isEqualTo(403);
    assertThat(ErrorCode.NOT_FOUND.getHttpStatus()).isEqualTo(404);
    assertThat(ErrorCode.CONFLICT.getHttpStatus()).isEqualTo(409);
    assertThat(ErrorCode.RATE_LIMITED.getHttpStatus()).isEqualTo(429);
    assertThat(ErrorCode.INTERNAL_ERROR.getHttpStatus()).isEqualTo(500);
    assertThat(ErrorCode.EXTERNAL_SERVICE_ERROR.getHttpStatus()).isEqualTo(502);
  }

  @Test
  void shouldHaveCorrectCode() {
    assertThat(ErrorCode.VALIDATION_ERROR.getCode()).isEqualTo("VALIDATION_ERROR");
    assertThat(ErrorCode.NOT_FOUND.getCode()).isEqualTo("NOT_FOUND");
    assertThat(ErrorCode.INTERNAL_ERROR.getCode()).isEqualTo("INTERNAL_ERROR");
  }

  @Test
  void shouldConvertToApiError() {
    var apiError = ErrorCode.VALIDATION_ERROR.toApiError("Test message", null);

    assertThat(apiError).containsEntry("code", "VALIDATION_ERROR");
    assertThat(apiError).containsEntry("message", "Test message");
    assertThat(apiError).containsKey("details");
  }

  @Test
  void shouldConvertToApiErrorWithDetails() {
    var details = java.util.Map.of("field", "email", "reason", "invalid format");
    var apiError = ErrorCode.VALIDATION_ERROR.toApiError("Test message", details);

    assertThat(apiError).containsEntry("code", "VALIDATION_ERROR");
    assertThat(apiError).containsEntry("message", "Test message");
    assertThat(apiError).containsEntry("details", details);
  }
}
