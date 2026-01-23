package com.aswa.common.model;

import com.aswa.common.exception.AswaException;
import com.aswa.common.exception.ErrorCode;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;

/**
 * Pagination request parameters.
 *
 * @param page the page number (0-indexed)
 * @param size the page size
 * @param sortBy the field to sort by
 * @param direction the sort direction
 */
public record PageRequest(
    int page, int size, @Nullable String sortBy, @NonNull SortDirection direction) {

  /** Default page number. */
  public static final int DEFAULT_PAGE = 0;

  /** Default page size. */
  public static final int DEFAULT_SIZE = 20;

  /** Maximum page size. */
  public static final int MAX_SIZE = 100;

  /**
   * Compact constructor with validation.
   *
   * @throws AswaException if validation fails
   */
  public PageRequest {
    if (page < 0) {
      throw AswaException.builder(ErrorCode.VALIDATION_ERROR, "Page number must be >= 0")
          .metadata("page", page)
          .build();
    }
    if (size < 1 || size > MAX_SIZE) {
      throw AswaException.builder(
              ErrorCode.VALIDATION_ERROR, "Page size must be between 1 and " + MAX_SIZE)
          .metadata("size", size)
          .build();
    }
  }

  /**
   * Creates a default PageRequest.
   *
   * @return a default PageRequest
   */
  @NonNull
  public static PageRequest ofDefaults() {
    return new PageRequest(DEFAULT_PAGE, DEFAULT_SIZE, null, SortDirection.DESC);
  }

  /**
   * Creates a PageRequest with the specified page and size.
   *
   * @param page the page number
   * @param size the page size
   * @return a new PageRequest
   */
  @NonNull
  public static PageRequest of(int page, int size) {
    return new PageRequest(page, size, null, SortDirection.DESC);
  }

  /**
   * Creates a PageRequest with all parameters.
   *
   * @param page the page number
   * @param size the page size
   * @param sortBy the field to sort by
   * @param direction the sort direction
   * @return a new PageRequest
   */
  @NonNull
  public static PageRequest of(
      int page, int size, @Nullable String sortBy, @NonNull SortDirection direction) {
    return new PageRequest(page, size, sortBy, direction);
  }

  /** Sort direction enum. */
  public enum SortDirection {
    ASC,
    DESC
  }
}
