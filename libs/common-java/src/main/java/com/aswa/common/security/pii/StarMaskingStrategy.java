package com.aswa.common.security.pii;

/**
 * Star masking strategy - shows last N characters.
 */
public class StarMaskingStrategy implements MaskingStrategy {

    private final int visibleChars;

    public StarMaskingStrategy(int visibleChars) {
        this.visibleChars = visibleChars;
    }

    @Override
    public String mask(String value) {
        if (value == null || value.length() <= visibleChars) {
            return "****";
        }

        int maskLength = value.length() - visibleChars;
        return "*".repeat(maskLength) + value.substring(maskLength);
    }
}
