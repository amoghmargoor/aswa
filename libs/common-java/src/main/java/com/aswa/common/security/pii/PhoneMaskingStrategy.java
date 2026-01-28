package com.aswa.common.security.pii;

/**
 * Phone number masking strategy.
 */
public class PhoneMaskingStrategy implements MaskingStrategy {

    @Override
    public String mask(String phone) {
        String digits = phone.replaceAll("[^0-9]", "");
        if (digits.length() < 4) {
            return "***-***-****";
        }
        return "***-***-" + digits.substring(digits.length() - 4);
    }
}
