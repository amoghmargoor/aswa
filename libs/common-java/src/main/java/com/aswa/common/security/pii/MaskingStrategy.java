package com.aswa.common.security.pii;

/**
 * Interface for PII masking strategies.
 */
public interface MaskingStrategy {

    /**
     * Mask a value.
     */
    String mask(String value);
}
