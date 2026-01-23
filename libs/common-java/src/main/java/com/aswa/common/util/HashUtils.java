package com.aswa.common.util;

import com.aswa.common.exception.AswaException;
import com.aswa.common.exception.ErrorCode;
import com.google.common.hash.Hashing;
import java.nio.charset.StandardCharsets;
import org.jspecify.annotations.NonNull;

/**
 * Hashing utilities for MD5 and SHA-256.
 *
 * <p>Provides hex-encoded hash strings for content identification and deduplication.
 */
public final class HashUtils {

  private HashUtils() {
    // Utility class
  }

  /**
   * Computes MD5 hash of a string.
   *
   * @param input the input string
   * @return hex-encoded MD5 hash
   */
  @NonNull
  public static String md5(@NonNull String input) {
    return md5(input.getBytes(StandardCharsets.UTF_8));
  }

  /**
   * Computes MD5 hash of a byte array.
   *
   * @param input the input bytes
   * @return hex-encoded MD5 hash
   */
  @NonNull
  @SuppressWarnings("deprecation") // MD5 is acceptable for non-security use cases
  public static String md5(@NonNull byte[] input) {
    try {
      return Hashing.md5().hashBytes(input).toString();
    } catch (Exception e) {
      throw AswaException.builder(ErrorCode.INTERNAL_ERROR, "Failed to compute MD5 hash")
          .cause(e)
          .build();
    }
  }

  /**
   * Computes SHA-256 hash of a string.
   *
   * @param input the input string
   * @return hex-encoded SHA-256 hash
   */
  @NonNull
  public static String sha256(@NonNull String input) {
    return sha256(input.getBytes(StandardCharsets.UTF_8));
  }

  /**
   * Computes SHA-256 hash of a byte array.
   *
   * @param input the input bytes
   * @return hex-encoded SHA-256 hash
   */
  @NonNull
  public static String sha256(@NonNull byte[] input) {
    try {
      return Hashing.sha256().hashBytes(input).toString();
    } catch (Exception e) {
      throw AswaException.builder(ErrorCode.INTERNAL_ERROR, "Failed to compute SHA-256 hash")
          .cause(e)
          .build();
    }
  }

  /**
   * Computes a consistent hash code for content versioning.
   *
   * <p>This uses SHA-256 and is suitable for detecting content changes.
   *
   * @param content the content to hash
   * @return hex-encoded content hash
   */
  @NonNull
  public static String contentHash(@NonNull String content) {
    return sha256(content);
  }
}
