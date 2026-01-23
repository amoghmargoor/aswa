package com.aswa.common.model;

import java.util.List;
import org.jspecify.annotations.NonNull;

/**
 * Paginated response wrapper.
 *
 * @param <T> the type of content
 * @param content the page content
 * @param totalElements the total number of elements
 * @param totalPages the total number of pages
 * @param currentPage the current page number
 * @param pageSize the page size
 */
public record PageResponse<T>(
    @NonNull List<T> content,
    long totalElements,
    int totalPages,
    int currentPage,
    int pageSize) {

  /**
   * Creates a PageResponse from the given parameters.
   *
   * @param <T> the type of content
   * @param content the page content
   * @param totalElements the total number of elements
   * @param currentPage the current page number
   * @param pageSize the page size
   * @return a new PageResponse
   */
  @NonNull
  public static <T> PageResponse<T> of(
      @NonNull List<T> content, long totalElements, int currentPage, int pageSize) {
    int totalPages = (int) Math.ceil((double) totalElements / pageSize);
    return new PageResponse<>(content, totalElements, totalPages, currentPage, pageSize);
  }

  /**
   * Creates an empty PageResponse.
   *
   * @param <T> the type of content
   * @param currentPage the current page number
   * @param pageSize the page size
   * @return an empty PageResponse
   */
  @NonNull
  public static <T> PageResponse<T> empty(int currentPage, int pageSize) {
    return new PageResponse<>(List.of(), 0, 0, currentPage, pageSize);
  }

  /**
   * Checks if this page has content.
   *
   * @return true if the page has content
   */
  public boolean hasContent() {
    return !content.isEmpty();
  }

  /**
   * Checks if there is a next page.
   *
   * @return true if there is a next page
   */
  public boolean hasNext() {
    return currentPage < totalPages - 1;
  }

  /**
   * Checks if there is a previous page.
   *
   * @return true if there is a previous page
   */
  public boolean hasPrevious() {
    return currentPage > 0;
  }

  /**
   * Checks if this is the first page.
   *
   * @return true if this is the first page
   */
  public boolean isFirst() {
    return currentPage == 0;
  }

  /**
   * Checks if this is the last page.
   *
   * @return true if this is the last page
   */
  public boolean isLast() {
    return currentPage == totalPages - 1 || totalPages == 0;
  }
}
