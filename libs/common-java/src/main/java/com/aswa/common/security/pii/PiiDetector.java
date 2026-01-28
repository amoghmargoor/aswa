package com.aswa.common.security.pii;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * PII detection service.
 */
@Service
public class PiiDetector {

    private static final Logger logger = LoggerFactory.getLogger(PiiDetector.class);

    private static final Map<PiiType, Pattern> PII_PATTERNS = Map.ofEntries(
        // Email
        Map.entry(PiiType.EMAIL,
            Pattern.compile("[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}", Pattern.CASE_INSENSITIVE)),

        // Phone numbers (various formats)
        Map.entry(PiiType.PHONE,
            Pattern.compile("(?:\\+?1[-.]?)?\\(?[0-9]{3}\\)?[-.]?[0-9]{3}[-.]?[0-9]{4}")),

        // SSN
        Map.entry(PiiType.SSN,
            Pattern.compile("\\b\\d{3}[-]?\\d{2}[-]?\\d{4}\\b")),

        // Credit card numbers
        Map.entry(PiiType.CREDIT_CARD,
            Pattern.compile("\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\\b")),

        // IP addresses
        Map.entry(PiiType.IP_ADDRESS,
            Pattern.compile("\\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\b")),

        // Passport numbers (generic)
        Map.entry(PiiType.PASSPORT,
            Pattern.compile("\\b[A-Z]{1,2}[0-9]{6,9}\\b")),

        // Date of birth patterns
        Map.entry(PiiType.DATE_OF_BIRTH,
            Pattern.compile("\\b(?:0?[1-9]|1[0-2])[/.-](?:0?[1-9]|[12][0-9]|3[01])[/.-](?:19|20)\\d{2}\\b")),

        // Bank account (generic)
        Map.entry(PiiType.BANK_ACCOUNT,
            Pattern.compile("\\b[0-9]{8,17}\\b")),

        // Driver's license (generic US)
        Map.entry(PiiType.DRIVERS_LICENSE,
            Pattern.compile("\\b[A-Z][0-9]{7,14}\\b"))
    );

    private static final Set<String> NAME_INDICATORS = Set.of(
        "name", "full name", "first name", "last name", "surname",
        "given name", "family name", "patient name", "customer name"
    );

    private static final Set<String> ADDRESS_INDICATORS = Set.of(
        "address", "street", "city", "state", "zip", "postal code",
        "country", "residence", "home address", "mailing address"
    );

    /**
     * Detect PII in text.
     */
    public List<PiiMatch> detect(String text) {
        if (text == null || text.isEmpty()) {
            return List.of();
        }

        List<PiiMatch> matches = new ArrayList<>();

        // Pattern-based detection
        for (Map.Entry<PiiType, Pattern> entry : PII_PATTERNS.entrySet()) {
            Matcher matcher = entry.getValue().matcher(text);
            while (matcher.find()) {
                matches.add(new PiiMatch(
                    entry.getKey(),
                    matcher.group(),
                    matcher.start(),
                    matcher.end(),
                    calculateConfidence(entry.getKey(), matcher.group())
                ));
            }
        }

        // Context-based detection for names and addresses
        String lowerText = text.toLowerCase();
        for (String indicator : NAME_INDICATORS) {
            int idx = lowerText.indexOf(indicator);
            if (idx >= 0) {
                matches.add(new PiiMatch(
                    PiiType.NAME,
                    "[Name detected by context]",
                    idx,
                    idx + indicator.length(),
                    0.6
                ));
            }
        }

        for (String indicator : ADDRESS_INDICATORS) {
            int idx = lowerText.indexOf(indicator);
            if (idx >= 0) {
                matches.add(new PiiMatch(
                    PiiType.ADDRESS,
                    "[Address detected by context]",
                    idx,
                    idx + indicator.length(),
                    0.6
                ));
            }
        }

        return matches;
    }

    /**
     * Check if text contains any PII.
     */
    public boolean containsPii(String text) {
        return !detect(text).isEmpty();
    }

    /**
     * Get PII types found in text.
     */
    public Set<PiiType> getPiiTypes(String text) {
        Set<PiiType> types = new HashSet<>();
        for (PiiMatch match : detect(text)) {
            types.add(match.type());
        }
        return types;
    }

    private double calculateConfidence(PiiType type, String match) {
        // Higher confidence for well-formed patterns
        return switch (type) {
            case EMAIL -> match.contains("@") ? 0.95 : 0.5;
            case SSN -> match.length() == 11 ? 0.9 : 0.7;
            case CREDIT_CARD -> luhnCheck(match) ? 0.95 : 0.5;
            case PHONE -> match.length() >= 10 ? 0.8 : 0.5;
            default -> 0.7;
        };
    }

    private boolean luhnCheck(String number) {
        String digits = number.replaceAll("[^0-9]", "");
        int sum = 0;
        boolean alternate = false;
        for (int i = digits.length() - 1; i >= 0; i--) {
            int n = Integer.parseInt(digits.substring(i, i + 1));
            if (alternate) {
                n *= 2;
                if (n > 9) n = (n % 10) + 1;
            }
            sum += n;
            alternate = !alternate;
        }
        return (sum % 10 == 0);
    }

    public record PiiMatch(
        PiiType type,
        String value,
        int startIndex,
        int endIndex,
        double confidence
    ) {}
}
