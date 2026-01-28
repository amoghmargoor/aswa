package com.aswa.common.security.pii;

/**
 * Email masking strategy.
 */
public class EmailMaskingStrategy implements MaskingStrategy {

    @Override
    public String mask(String email) {
        if (email == null || !email.contains("@")) {
            return "***@***.***";
        }

        String[] parts = email.split("@");
        String local = parts[0];
        String domain = parts[1];

        String maskedLocal = local.length() <= 2
            ? "***"
            : local.charAt(0) + "***" + local.charAt(local.length() - 1);

        String[] domainParts = domain.split("\\.");
        String maskedDomain = domainParts[0].charAt(0) + "***." +
            domainParts[domainParts.length - 1];

        return maskedLocal + "@" + maskedDomain;
    }
}
