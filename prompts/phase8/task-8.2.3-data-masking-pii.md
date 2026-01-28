# Task 8.2.3: Data Security - Data Masking & PII Handling

## Context

You are implementing data security for ASWA. Encryption in transit is complete. Now we need data masking and PII handling.

## Objective

Create PII handling implementation that:
1. Detects and classifies PII in documents
2. Masks sensitive data in logs and outputs
3. Implements data redaction for exports
4. Supports configurable masking rules
5. Enables audit trails for PII access

## Requirements

### 1. Create `/libs/common-java/src/main/java/com/aswa/common/security/pii/PiiDetector.java`
```java
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
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/security/pii/PiiType.java`
```java
package com.aswa.common.security.pii;

/**
 * Types of Personally Identifiable Information.
 */
public enum PiiType {
    EMAIL("email", "Email Address", SensitivityLevel.MEDIUM),
    PHONE("phone", "Phone Number", SensitivityLevel.MEDIUM),
    SSN("ssn", "Social Security Number", SensitivityLevel.HIGH),
    CREDIT_CARD("credit_card", "Credit Card Number", SensitivityLevel.HIGH),
    IP_ADDRESS("ip_address", "IP Address", SensitivityLevel.LOW),
    NAME("name", "Personal Name", SensitivityLevel.MEDIUM),
    ADDRESS("address", "Physical Address", SensitivityLevel.MEDIUM),
    DATE_OF_BIRTH("dob", "Date of Birth", SensitivityLevel.MEDIUM),
    PASSPORT("passport", "Passport Number", SensitivityLevel.HIGH),
    DRIVERS_LICENSE("drivers_license", "Driver's License", SensitivityLevel.HIGH),
    BANK_ACCOUNT("bank_account", "Bank Account Number", SensitivityLevel.HIGH),
    MEDICAL_RECORD("medical_record", "Medical Record Number", SensitivityLevel.HIGH);

    private final String code;
    private final String displayName;
    private final SensitivityLevel sensitivityLevel;

    PiiType(String code, String displayName, SensitivityLevel sensitivityLevel) {
        this.code = code;
        this.displayName = displayName;
        this.sensitivityLevel = sensitivityLevel;
    }

    public String getCode() { return code; }
    public String getDisplayName() { return displayName; }
    public SensitivityLevel getSensitivityLevel() { return sensitivityLevel; }

    public enum SensitivityLevel {
        LOW, MEDIUM, HIGH, CRITICAL
    }
}
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/security/pii/DataMasker.java`
```java
package com.aswa.common.security.pii;

import org.springframework.stereotype.Service;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

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
```

### 4. Create `/libs/common-java/src/main/java/com/aswa/common/security/pii/MaskingConfig.java`
```java
package com.aswa.common.security.pii;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * Configuration for PII masking strategies.
 */
@Component
@ConfigurationProperties(prefix = "pii.masking")
public class MaskingConfig {

    private Map<String, StrategyConfig> strategies = new HashMap<>();
    private boolean enabled = true;
    private boolean auditAccess = true;

    public Map<String, StrategyConfig> getStrategies() {
        return strategies;
    }

    public void setStrategies(Map<String, StrategyConfig> strategies) {
        this.strategies = strategies;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public boolean isAuditAccess() {
        return auditAccess;
    }

    public void setAuditAccess(boolean auditAccess) {
        this.auditAccess = auditAccess;
    }

    public MaskingStrategy getStrategy(PiiType type) {
        StrategyConfig config = strategies.get(type.getCode());
        if (config == null) {
            return getDefaultStrategy(type);
        }
        return createStrategy(config);
    }

    private MaskingStrategy getDefaultStrategy(PiiType type) {
        return switch (type) {
            case EMAIL -> new EmailMaskingStrategy();
            case PHONE -> new PhoneMaskingStrategy();
            case SSN -> new SsnMaskingStrategy();
            case CREDIT_CARD -> new CreditCardMaskingStrategy();
            default -> new StarMaskingStrategy(4);
        };
    }

    private MaskingStrategy createStrategy(StrategyConfig config) {
        return switch (config.getType()) {
            case "email" -> new EmailMaskingStrategy();
            case "phone" -> new PhoneMaskingStrategy();
            case "ssn" -> new SsnMaskingStrategy();
            case "credit_card" -> new CreditCardMaskingStrategy();
            case "star" -> new StarMaskingStrategy(config.getVisibleChars());
            case "redact" -> new RedactMaskingStrategy(config.getLabel());
            default -> new StarMaskingStrategy(4);
        };
    }

    public static class StrategyConfig {
        private String type;
        private int visibleChars = 4;
        private String label = "REDACTED";

        public String getType() { return type; }
        public void setType(String type) { this.type = type; }
        public int getVisibleChars() { return visibleChars; }
        public void setVisibleChars(int visibleChars) { this.visibleChars = visibleChars; }
        public String getLabel() { return label; }
        public void setLabel(String label) { this.label = label; }
    }
}
```

### 5. Create `/libs/common-python/src/aswa_common/pii.py`
```python
"""PII detection and masking for Python services."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger()


class PiiType(Enum):
    """Types of PII."""
    EMAIL = ("email", "Email Address", "medium")
    PHONE = ("phone", "Phone Number", "medium")
    SSN = ("ssn", "Social Security Number", "high")
    CREDIT_CARD = ("credit_card", "Credit Card Number", "high")
    IP_ADDRESS = ("ip_address", "IP Address", "low")
    NAME = ("name", "Personal Name", "medium")
    ADDRESS = ("address", "Physical Address", "medium")
    DATE_OF_BIRTH = ("dob", "Date of Birth", "medium")

    def __init__(self, code: str, display_name: str, sensitivity: str):
        self.code = code
        self.display_name = display_name
        self.sensitivity = sensitivity


@dataclass
class PiiMatch:
    """Detected PII match."""
    pii_type: PiiType
    value: str
    start: int
    end: int
    confidence: float


# PII detection patterns
PII_PATTERNS: dict[PiiType, re.Pattern] = {
    PiiType.EMAIL: re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        re.IGNORECASE
    ),
    PiiType.PHONE: re.compile(
        r"(?:\+?1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}"
    ),
    PiiType.SSN: re.compile(r"\b\d{3}[-]?\d{2}[-]?\d{4}\b"),
    PiiType.CREDIT_CARD: re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"
        r"5[1-5][0-9]{14}|"
        r"3[47][0-9]{13}|"
        r"6(?:011|5[0-9]{2})[0-9]{12})\b"
    ),
    PiiType.IP_ADDRESS: re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    ),
}


class PiiDetector:
    """Detects PII in text."""

    def __init__(self):
        self.name_indicators = {
            "name", "full name", "first name", "last name",
            "surname", "given name", "patient name"
        }
        self.address_indicators = {
            "address", "street", "city", "state", "zip",
            "postal code", "residence"
        }

    def detect(self, text: str) -> list[PiiMatch]:
        """Detect all PII in text."""
        if not text:
            return []

        matches = []

        # Pattern-based detection
        for pii_type, pattern in PII_PATTERNS.items():
            for match in pattern.finditer(text):
                matches.append(PiiMatch(
                    pii_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=self._calculate_confidence(pii_type, match.group()),
                ))

        # Context-based detection
        lower_text = text.lower()
        for indicator in self.name_indicators:
            if indicator in lower_text:
                idx = lower_text.index(indicator)
                matches.append(PiiMatch(
                    pii_type=PiiType.NAME,
                    value="[Name detected by context]",
                    start=idx,
                    end=idx + len(indicator),
                    confidence=0.6,
                ))
                break

        return matches

    def contains_pii(self, text: str) -> bool:
        """Check if text contains any PII."""
        return len(self.detect(text)) > 0

    def get_pii_types(self, text: str) -> set[PiiType]:
        """Get types of PII found in text."""
        return {m.pii_type for m in self.detect(text)}

    def _calculate_confidence(self, pii_type: PiiType, value: str) -> float:
        """Calculate confidence score for detection."""
        if pii_type == PiiType.EMAIL:
            return 0.95 if "@" in value else 0.5
        elif pii_type == PiiType.SSN:
            return 0.9 if len(value) == 11 else 0.7
        elif pii_type == PiiType.CREDIT_CARD:
            return 0.95 if self._luhn_check(value) else 0.5
        return 0.7

    def _luhn_check(self, number: str) -> bool:
        """Validate credit card number using Luhn algorithm."""
        digits = re.sub(r"[^0-9]", "", number)
        total = 0
        alternate = False
        for i in range(len(digits) - 1, -1, -1):
            n = int(digits[i])
            if alternate:
                n *= 2
                if n > 9:
                    n = (n % 10) + 1
            total += n
            alternate = not alternate
        return total % 10 == 0


class DataMasker:
    """Masks PII in text."""

    def __init__(self, detector: Optional[PiiDetector] = None):
        self.detector = detector or PiiDetector()

    def mask_pii(self, text: str) -> str:
        """Mask all detected PII in text."""
        if not text:
            return text

        matches = self.detector.detect(text)
        if not matches:
            return text

        # Sort by position (reverse) to replace from end
        matches.sort(key=lambda m: m.start, reverse=True)

        result = text
        for match in matches:
            masked = self.mask_value(match.pii_type, match.value)
            result = result[:match.start] + masked + result[match.end:]

        return result

    def mask_value(self, pii_type: PiiType, value: str) -> str:
        """Mask a specific value based on PII type."""
        if pii_type == PiiType.EMAIL:
            return self.mask_email(value)
        elif pii_type == PiiType.PHONE:
            return self.mask_phone(value)
        elif pii_type == PiiType.SSN:
            return self.mask_ssn(value)
        elif pii_type == PiiType.CREDIT_CARD:
            return self.mask_credit_card(value)
        else:
            return f"[{pii_type.code.upper()}]"

    def mask_email(self, email: str) -> str:
        """Mask email address."""
        if "@" not in email:
            return "***@***.***"
        local, domain = email.split("@", 1)
        masked_local = local[0] + "***" + local[-1] if len(local) > 2 else "***"
        domain_parts = domain.split(".")
        masked_domain = domain_parts[0][0] + "***." + domain_parts[-1]
        return f"{masked_local}@{masked_domain}"

    def mask_phone(self, phone: str) -> str:
        """Mask phone number (show last 4 digits)."""
        digits = re.sub(r"[^0-9]", "", phone)
        return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "***-***-****"

    def mask_ssn(self, ssn: str) -> str:
        """Mask SSN (show last 4 digits)."""
        digits = re.sub(r"[^0-9]", "", ssn)
        return f"***-**-{digits[-4:]}" if len(digits) >= 4 else "***-**-****"

    def mask_credit_card(self, card: str) -> str:
        """Mask credit card (show last 4 digits)."""
        digits = re.sub(r"[^0-9]", "", card)
        return f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else "****-****-****-****"

    def mask_for_logging(self, text: str) -> str:
        """Mask text for safe logging (full redaction)."""
        matches = self.detector.detect(text)
        if not matches:
            return text

        matches.sort(key=lambda m: m.start, reverse=True)
        result = text
        for match in matches:
            result = result[:match.start] + f"[{match.pii_type.code.upper()}]" + result[match.end:]
        return result


# Logging filter for PII
class PiiLoggingFilter:
    """Filter PII from log messages."""

    def __init__(self):
        self.masker = DataMasker()

    def __call__(self, logger, method_name, event_dict):
        """Filter event dict for PII."""
        for key, value in event_dict.items():
            if isinstance(value, str):
                event_dict[key] = self.masker.mask_for_logging(value)
        return event_dict


def configure_pii_logging():
    """Configure structlog to filter PII."""
    structlog.configure(
        processors=[
            PiiLoggingFilter(),
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
```

## Test Requirements

Create tests:

1. **PiiDetectorTest.java** - Test PII pattern detection
2. **DataMaskerTest.java** - Test masking strategies
3. **test_pii.py** - Python PII detection and masking tests
4. **Integration tests** - Test PII handling in API responses

## Verification

1. Run tests: `./gradlew test` and `pytest`
2. Verify PII detection accuracy
3. Test masking in API responses
4. Verify PII filtered from logs
5. Test audit trail for PII access
