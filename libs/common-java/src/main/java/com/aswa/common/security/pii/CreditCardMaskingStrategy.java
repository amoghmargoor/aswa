package com.aswa.common.security.pii;

/**
 * Credit card masking strategy.
 */
public class CreditCardMaskingStrategy implements MaskingStrategy {

    @Override
    public String mask(String cardNumber) {
        String digits = cardNumber.replaceAll("[^0-9]", "");
        if (digits.length() < 4) {
            return "****-****-****-****";
        }
        return "****-****-****-" + digits.substring(digits.length() - 4);
    }
}
