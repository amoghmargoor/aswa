package com.aswa.common.security.pii;

/**
 * Full redaction masking strategy.
 */
public class RedactMaskingStrategy implements MaskingStrategy {

    private final String label;

    public RedactMaskingStrategy(String label) {
        this.label = label;
    }

    @Override
    public String mask(String value) {
        return "[" + label + "]";
    }
}
