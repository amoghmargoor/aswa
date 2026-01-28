package com.aswa.common.security.pii;

/**
 * SSN masking strategy.
 */
public class SsnMaskingStrategy implements MaskingStrategy {

    @Override
    public String mask(String ssn) {
        String digits = ssn.replaceAll("[^0-9]", "");
        if (digits.length() < 4) {
            return "***-**-****";
        }
        return "***-**-" + digits.substring(digits.length() - 4);
    }
}
