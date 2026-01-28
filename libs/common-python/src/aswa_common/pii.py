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
