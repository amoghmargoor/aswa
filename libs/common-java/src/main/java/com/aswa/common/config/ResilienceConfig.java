package com.aswa.common.config;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.ratelimiter.RateLimiter;
import io.github.resilience4j.ratelimiter.RateLimiterConfig;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import java.time.Duration;
import org.jspecify.annotations.NonNull;

/**
 * Factory for creating resilience patterns (circuit breaker, retry, rate limiter).
 *
 * <p>Provides sensible defaults for production use with configurable parameters.
 */
public final class ResilienceConfig {

  private ResilienceConfig() {
    // Utility class
  }

  /**
   * Creates a circuit breaker with the specified configuration.
   *
   * @param name the circuit breaker name
   * @param failureRateThreshold the failure rate threshold (0-100)
   * @param waitDurationInSeconds the wait duration before transitioning to half-open
   * @return a configured CircuitBreaker
   */
  @NonNull
  public static CircuitBreaker createCircuitBreaker(
      @NonNull String name, float failureRateThreshold, long waitDurationInSeconds) {
    CircuitBreakerConfig config =
        CircuitBreakerConfig.custom()
            .failureRateThreshold(failureRateThreshold)
            .waitDurationInOpenState(Duration.ofSeconds(waitDurationInSeconds))
            .slidingWindowSize(10)
            .minimumNumberOfCalls(5)
            .permittedNumberOfCallsInHalfOpenState(3)
            .build();

    return CircuitBreaker.of(name, config);
  }

  /**
   * Creates a circuit breaker with default configuration.
   *
   * <p>Defaults: 50% failure rate threshold, 60 second wait duration
   *
   * @param name the circuit breaker name
   * @return a configured CircuitBreaker
   */
  @NonNull
  public static CircuitBreaker createCircuitBreaker(@NonNull String name) {
    return createCircuitBreaker(name, 50.0f, 60);
  }

  /**
   * Creates a retry policy with the specified configuration.
   *
   * @param name the retry name
   * @param maxAttempts the maximum number of retry attempts
   * @param waitDurationInMillis the wait duration between retries
   * @return a configured Retry
   */
  @NonNull
  public static Retry createRetry(
      @NonNull String name, int maxAttempts, long waitDurationInMillis) {
    RetryConfig config =
        RetryConfig.custom()
            .maxAttempts(maxAttempts)
            .waitDuration(Duration.ofMillis(waitDurationInMillis))
            .build();

    return Retry.of(name, config);
  }

  /**
   * Creates a retry policy with exponential backoff.
   *
   * @param name the retry name
   * @param maxAttempts the maximum number of retry attempts
   * @param initialWaitDurationInMillis the initial wait duration
   * @param multiplier the exponential backoff multiplier
   * @return a configured Retry
   */
  @NonNull
  public static Retry createRetryWithExponentialBackoff(
      @NonNull String name, int maxAttempts, long initialWaitDurationInMillis, double multiplier) {
    RetryConfig config =
        RetryConfig.custom()
            .maxAttempts(maxAttempts)
            .waitDuration(Duration.ofMillis(initialWaitDurationInMillis))
            .intervalFunction(
                attempt -> (long) (initialWaitDurationInMillis * Math.pow(multiplier, attempt - 1)))
            .build();

    return Retry.of(name, config);
  }

  /**
   * Creates a retry policy with default configuration.
   *
   * <p>Defaults: 3 attempts, 1000ms wait duration with 2x exponential backoff
   *
   * @param name the retry name
   * @return a configured Retry
   */
  @NonNull
  public static Retry createRetry(@NonNull String name) {
    return createRetryWithExponentialBackoff(name, 3, 1000, 2.0);
  }

  /**
   * Creates a rate limiter with the specified configuration.
   *
   * @param name the rate limiter name
   * @param limitForPeriod the number of permits per period
   * @param limitRefreshPeriodInMillis the period duration in milliseconds
   * @return a configured RateLimiter
   */
  @NonNull
  public static RateLimiter createRateLimiter(
      @NonNull String name, int limitForPeriod, long limitRefreshPeriodInMillis) {
    RateLimiterConfig config =
        RateLimiterConfig.custom()
            .limitForPeriod(limitForPeriod)
            .limitRefreshPeriod(Duration.ofMillis(limitRefreshPeriodInMillis))
            .timeoutDuration(Duration.ofMillis(500))
            .build();

    return RateLimiter.of(name, config);
  }

  /**
   * Creates a rate limiter with default configuration.
   *
   * <p>Defaults: 100 requests per second
   *
   * @param name the rate limiter name
   * @return a configured RateLimiter
   */
  @NonNull
  public static RateLimiter createRateLimiter(@NonNull String name) {
    return createRateLimiter(name, 100, 1000);
  }
}
