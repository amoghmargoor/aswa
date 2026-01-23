package com.aswa.common.util;

import com.aswa.common.exception.AswaException;
import com.aswa.common.exception.ErrorCode;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.text.SimpleDateFormat;
import org.jspecify.annotations.NonNull;

/**
 * JSON serialization and deserialization utilities.
 *
 * <p>This class provides a singleton ObjectMapper configured for ASWA use cases.
 */
public final class JsonUtils {

  private static final ObjectMapper MAPPER = createObjectMapper();

  private JsonUtils() {
    // Utility class
  }

  /**
   * Gets the singleton ObjectMapper instance.
   *
   * @return the ObjectMapper
   */
  @NonNull
  public static ObjectMapper getMapper() {
    return MAPPER;
  }

  /**
   * Serializes an object to JSON string.
   *
   * @param object the object to serialize
   * @return JSON string
   * @throws AswaException if serialization fails
   */
  @NonNull
  public static String toJson(@NonNull Object object) {
    try {
      return MAPPER.writeValueAsString(object);
    } catch (JsonProcessingException e) {
      throw AswaException.builder(ErrorCode.INTERNAL_ERROR, "Failed to serialize object to JSON")
          .cause(e)
          .metadata("objectType", object.getClass().getName())
          .build();
    }
  }

  /**
   * Serializes an object to pretty-printed JSON string.
   *
   * @param object the object to serialize
   * @return pretty-printed JSON string
   * @throws AswaException if serialization fails
   */
  @NonNull
  public static String toPrettyJson(@NonNull Object object) {
    try {
      return MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(object);
    } catch (JsonProcessingException e) {
      throw AswaException.builder(ErrorCode.INTERNAL_ERROR, "Failed to serialize object to JSON")
          .cause(e)
          .metadata("objectType", object.getClass().getName())
          .build();
    }
  }

  /**
   * Deserializes a JSON string to an object.
   *
   * @param <T> the target type
   * @param json the JSON string
   * @param clazz the target class
   * @return the deserialized object
   * @throws AswaException if deserialization fails
   */
  @NonNull
  public static <T> T fromJson(@NonNull String json, @NonNull Class<T> clazz) {
    try {
      return MAPPER.readValue(json, clazz);
    } catch (JsonProcessingException e) {
      throw AswaException.builder(ErrorCode.VALIDATION_ERROR, "Failed to deserialize JSON")
          .cause(e)
          .metadata("targetType", clazz.getName())
          .build();
    }
  }

  /**
   * Deserializes a JSON string to an object using TypeReference.
   *
   * @param <T> the target type
   * @param json the JSON string
   * @param typeRef the type reference
   * @return the deserialized object
   * @throws AswaException if deserialization fails
   */
  @NonNull
  public static <T> T fromJson(@NonNull String json, @NonNull TypeReference<T> typeRef) {
    try {
      return MAPPER.readValue(json, typeRef);
    } catch (JsonProcessingException e) {
      throw AswaException.builder(ErrorCode.VALIDATION_ERROR, "Failed to deserialize JSON")
          .cause(e)
          .metadata("targetType", typeRef.getType().getTypeName())
          .build();
    }
  }

  /**
   * Converts an object to another type using JSON serialization/deserialization.
   *
   * @param <T> the target type
   * @param object the source object
   * @param clazz the target class
   * @return the converted object
   * @throws AswaException if conversion fails
   */
  @NonNull
  public static <T> T convert(@NonNull Object object, @NonNull Class<T> clazz) {
    return MAPPER.convertValue(object, clazz);
  }

  private static ObjectMapper createObjectMapper() {
    ObjectMapper mapper = new ObjectMapper();

    // Register Java 8 date/time module
    mapper.registerModule(new JavaTimeModule());

    // Configure serialization
    mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    mapper.disable(SerializationFeature.FAIL_ON_EMPTY_BEANS);
    mapper.setDateFormat(new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ"));

    // Configure deserialization
    mapper.disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
    mapper.enable(DeserializationFeature.READ_UNKNOWN_ENUM_VALUES_AS_NULL);

    return mapper;
  }
}
