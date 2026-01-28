package com.aswa.common.security.pii;

import org.springframework.stereotype.Service;

import java.util.*;

/**
 * Data masking service for PII.
 */
@Service
public class DataMasker {

    private final PiiDetector piiDetector;
    private final MaskingConfig config;

    public DataMasker(PiiDetector piiDetector, MaskingConfig config) {
        this.piiDetector = piiDetector;
        this.config = config;
    }

    /**
     * Mask all detected PII in text.
     */
    public String maskPii(String text) {
        if (text == null || text.isEmpty()) {
            return text;
        }

        List<PiiDetector.PiiMatch> matches = piiDetector.detect(text);
        if (matches.isEmpty()) {
            return text;
        }

        // Sort by start index in reverse to replace from end
        matches.sort((a, b) -> Integer.compare(b.startIndex(), a.startIndex()));

        StringBuilder result = new StringBuilder(text);
        for (PiiDetector.PiiMatch match : matches) {
            String masked = maskValue(match.type(), match.value());
            result.replace(match.startIndex(), match.endIndex(), masked);
        }

        return result.toString();
    }

    /**
     * Mask specific PII type in text.
     */
    public String maskPiiType(String text, PiiType type) {
        if (text == null || text.isEmpty()) {
            return text;
        }

        List<PiiDetector.PiiMatch> matches = piiDetector.detect(text).stream()
            .filter(m -> m.type() == type)
            .toList();

        if (matches.isEmpty()) {
            return text;
        }

        List<PiiDetector.PiiMatch> sorted = new ArrayList<>(matches);
        sorted.sort((a, b) -> Integer.compare(b.startIndex(), a.startIndex()));

        StringBuilder result = new StringBuilder(text);
        for (PiiDetector.PiiMatch match : sorted) {
            String masked = maskValue(match.type(), match.value());
            result.replace(match.startIndex(), match.endIndex(), masked);
        }

        return result.toString();
    }

    /**
     * Mask a specific value based on PII type.
     */
    public String maskValue(PiiType type, String value) {
        if (value == null || value.isEmpty()) {
            return value;
        }

        MaskingStrategy strategy = config.getStrategy(type);
        return strategy.mask(value);
    }

    /**
     * Mask email address.
     */
    public String maskEmail(String email) {
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

    /**
     * Mask phone number (show last 4 digits).
     */
    public String maskPhone(String phone) {
        String digits = phone.replaceAll("[^0-9]", "");
        if (digits.length() < 4) {
            return "***-***-****";
        }
        return "***-***-" + digits.substring(digits.length() - 4);
    }

    /**
     * Mask credit card (show last 4 digits).
     */
    public String maskCreditCard(String cardNumber) {
        String digits = cardNumber.replaceAll("[^0-9]", "");
        if (digits.length() < 4) {
            return "****-****-****-****";
        }
        return "****-****-****-" + digits.substring(digits.length() - 4);
    }

    /**
     * Mask SSN (show last 4 digits).
     */
    public String maskSsn(String ssn) {
        String digits = ssn.replaceAll("[^0-9]", "");
        if (digits.length() < 4) {
            return "***-**-****";
        }
        return "***-**-" + digits.substring(digits.length() - 4);
    }

    /**
     * Full redaction.
     */
    public String redact(String value, PiiType type) {
        return "[REDACTED:" + type.getCode().toUpperCase() + "]";
    }

    /**
     * Mask for logging (never show actual values).
     */
    public String maskForLogging(String text) {
        List<PiiDetector.PiiMatch> matches = piiDetector.detect(text);
        if (matches.isEmpty()) {
            return text;
        }

        List<PiiDetector.PiiMatch> sorted = new ArrayList<>(matches);
        sorted.sort((a, b) -> Integer.compare(b.startIndex(), a.startIndex()));

        StringBuilder result = new StringBuilder(text);
        for (PiiDetector.PiiMatch match : sorted) {
            result.replace(
                match.startIndex(),
                match.endIndex(),
                "[" + match.type().getCode().toUpperCase() + "]"
            );
        }

        return result.toString();
    }
}
