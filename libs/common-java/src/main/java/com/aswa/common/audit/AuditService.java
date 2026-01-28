package com.aswa.common.audit;

import com.aswa.common.auth.UserPrincipal;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.opentelemetry.api.trace.Span;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import jakarta.servlet.http.HttpServletRequest;
import java.security.MessageDigest;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Audit logging service.
 */
@Service
public class AuditService {

    private static final Logger logger = LoggerFactory.getLogger(AuditService.class);
    private static final String AUDIT_TOPIC = "aswa.audit.events";

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final AuditRepository auditRepository;
    private final ObjectMapper objectMapper;

    public AuditService(
            KafkaTemplate<String, String> kafkaTemplate,
            AuditRepository auditRepository,
            ObjectMapper objectMapper) {
        this.kafkaTemplate = kafkaTemplate;
        this.auditRepository = auditRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Log an audit event.
     */
    public void log(AuditEvent event) {
        try {
            // Add integrity hash
            String eventJson = objectMapper.writeValueAsString(event);
            String hash = computeHash(eventJson);

            AuditEventWithHash eventWithHash = new AuditEventWithHash(event, hash);
            String finalJson = objectMapper.writeValueAsString(eventWithHash);

            // Send to Kafka for async processing
            kafkaTemplate.send(AUDIT_TOPIC, event.tenantId(), finalJson);

            // Also log to structured logger
            logger.info("AUDIT: {} {} {} on {} {}",
                event.action().getCode(),
                event.result(),
                event.userId(),
                event.resourceType(),
                event.resourceId());

        } catch (Exception e) {
            logger.error("Failed to log audit event", e);
        }
    }

    /**
     * Log with current user context.
     */
    public void log(
            AuditAction action,
            AuditCategory category,
            String resourceType,
            String resourceId,
            AuditResult result,
            Map<String, Object> metadata) {

        UserPrincipal user = getCurrentUser();
        HttpServletRequest request = getCurrentRequest();

        AuditEvent event = AuditEvent.builder()
            .action(action)
            .category(category)
            .resourceType(resourceType)
            .resourceId(resourceId)
            .result(result)
            .tenantId(user != null ? user.getTenantId() : null)
            .userId(user != null ? user.getId() : null)
            .userEmail(user != null ? user.getEmail() : null)
            .userRole(user != null ? user.getRole() : null)
            .ipAddress(request != null ? getClientIp(request) : null)
            .userAgent(request != null ? request.getHeader("User-Agent") : null)
            .sessionId(request != null ? request.getHeader("X-Session-Id") : null)
            .traceId(Span.current().getSpanContext().getTraceId())
            .metadata(metadata)
            .build();

        log(event);
    }

    /**
     * Log data modification with before/after state.
     */
    @SuppressWarnings("unchecked")
    public void logModification(
            AuditAction action,
            String resourceType,
            String resourceId,
            Object before,
            Object after) {

        UserPrincipal user = getCurrentUser();
        HttpServletRequest request = getCurrentRequest();

        try {
            AuditEvent event = AuditEvent.builder()
                .action(action)
                .category(AuditCategory.DATA_MODIFICATION)
                .resourceType(resourceType)
                .resourceId(resourceId)
                .result(AuditResult.SUCCESS)
                .tenantId(user != null ? user.getTenantId() : null)
                .userId(user != null ? user.getId() : null)
                .userEmail(user != null ? user.getEmail() : null)
                .userRole(user != null ? user.getRole() : null)
                .ipAddress(request != null ? getClientIp(request) : null)
                .userAgent(request != null ? request.getHeader("User-Agent") : null)
                .traceId(Span.current().getSpanContext().getTraceId())
                .before(objectMapper.convertValue(before, Map.class))
                .after(objectMapper.convertValue(after, Map.class))
                .build();

            log(event);
        } catch (Exception e) {
            logger.error("Failed to log modification audit", e);
        }
    }

    /**
     * Log failed operation.
     */
    public void logFailure(
            AuditAction action,
            AuditCategory category,
            String resourceType,
            String resourceId,
            String errorMessage) {

        UserPrincipal user = getCurrentUser();
        HttpServletRequest request = getCurrentRequest();

        AuditEvent event = AuditEvent.builder()
            .action(action)
            .category(category)
            .resourceType(resourceType)
            .resourceId(resourceId)
            .result(AuditResult.FAILURE)
            .errorMessage(errorMessage)
            .tenantId(user != null ? user.getTenantId() : null)
            .userId(user != null ? user.getId() : null)
            .userEmail(user != null ? user.getEmail() : null)
            .userRole(user != null ? user.getRole() : null)
            .ipAddress(request != null ? getClientIp(request) : null)
            .userAgent(request != null ? request.getHeader("User-Agent") : null)
            .traceId(Span.current().getSpanContext().getTraceId())
            .build();

        log(event);
    }

    /**
     * Search audit logs.
     */
    public CompletableFuture<AuditSearchResult> search(AuditSearchCriteria criteria) {
        return auditRepository.search(criteria);
    }

    private String computeHash(String data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(data.getBytes());
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (Exception e) {
            return null;
        }
    }

    private UserPrincipal getCurrentUser() {
        // Get from SecurityContext
        return null; // Implementation depends on security setup
    }

    private HttpServletRequest getCurrentRequest() {
        try {
            ServletRequestAttributes attrs =
                (ServletRequestAttributes) RequestContextHolder.currentRequestAttributes();
            return attrs.getRequest();
        } catch (Exception e) {
            return null;
        }
    }

    private String getClientIp(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
            return xForwardedFor.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    public record AuditEventWithHash(AuditEvent event, String hash) {}
}
