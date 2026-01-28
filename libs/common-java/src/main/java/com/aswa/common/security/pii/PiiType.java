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
