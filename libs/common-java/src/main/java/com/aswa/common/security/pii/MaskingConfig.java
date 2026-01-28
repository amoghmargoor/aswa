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
