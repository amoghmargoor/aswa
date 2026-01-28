package com.aswa.common.compliance;

import java.util.List;

/**
 * Compliance framework definitions.
 */
public enum ComplianceFramework {
    SOC2_TYPE1("SOC 2 Type I", "Service Organization Control 2 Type I"),
    SOC2_TYPE2("SOC 2 Type II", "Service Organization Control 2 Type II"),
    GDPR("GDPR", "General Data Protection Regulation"),
    HIPAA("HIPAA", "Health Insurance Portability and Accountability Act"),
    PCI_DSS("PCI DSS", "Payment Card Industry Data Security Standard"),
    ISO27001("ISO 27001", "Information Security Management"),
    CCPA("CCPA", "California Consumer Privacy Act"),
    CUSTOM("Custom", "Custom compliance framework");

    private final String name;
    private final String fullName;

    ComplianceFramework(String name, String fullName) {
        this.name = name;
        this.fullName = fullName;
    }

    public String getName() { return name; }
    public String getFullName() { return fullName; }

    public List<String> getRequiredControls() {
        return switch (this) {
            case SOC2_TYPE1, SOC2_TYPE2 -> List.of(
                "CC1.1", "CC1.2", "CC1.3", "CC1.4", "CC1.5",
                "CC2.1", "CC2.2", "CC2.3",
                "CC3.1", "CC3.2", "CC3.3", "CC3.4",
                "CC4.1", "CC4.2",
                "CC5.1", "CC5.2", "CC5.3",
                "CC6.1", "CC6.2", "CC6.3", "CC6.4", "CC6.5", "CC6.6", "CC6.7", "CC6.8",
                "CC7.1", "CC7.2", "CC7.3", "CC7.4", "CC7.5",
                "CC8.1",
                "CC9.1", "CC9.2"
            );
            case GDPR -> List.of(
                "ART5", "ART6", "ART7", "ART12", "ART13", "ART14",
                "ART15", "ART16", "ART17", "ART18", "ART20",
                "ART25", "ART30", "ART32", "ART33", "ART34", "ART35"
            );
            case HIPAA -> List.of(
                "164.308", "164.310", "164.312", "164.314", "164.316"
            );
            default -> List.of();
        };
    }
}
