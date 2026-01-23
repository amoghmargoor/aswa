package com.aswa.gateway.config;

import com.aswa.gateway.security.TenantContext;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import reactor.core.publisher.Mono;

import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Web configuration for filters and request handling.
 *
 * Provides:
 * - Request logging with request ID tracking
 * - Tenant context extraction from JWT
 * - MDC logging context setup
 */
@Slf4j
@Configuration
public class WebConfig {

    @Bean
    public WebFilter requestLoggingFilter() {
        return (exchange, chain) -> {
            String requestId = UUID.randomUUID().toString();
            String method = exchange.getRequest().getMethod().toString();
            String path = exchange.getRequest().getPath().value();

            MDC.put("requestId", requestId);
            exchange.getResponse().getHeaders().add("X-Request-ID", requestId);

            long startTime = System.currentTimeMillis();
            log.info("Request started: {} {}", method, path);

            return chain.filter(exchange)
                    .doFinally(signalType -> {
                        long duration = System.currentTimeMillis() - startTime;
                        int statusCode = exchange.getResponse().getStatusCode() != null
                                ? exchange.getResponse().getStatusCode().value()
                                : 0;
                        log.info("Request completed: {} {} - {} - {}ms",
                                method, path, statusCode, duration);
                        MDC.clear();
                    });
        };
    }

    @Bean
    public WebFilter tenantContextFilter() {
        return (exchange, chain) -> ReactiveSecurityContextHolder.getContext()
                .flatMap(securityContext -> {
                    Authentication authentication = securityContext.getAuthentication();

                    if (authentication instanceof JwtAuthenticationToken jwtAuth) {
                        return extractTenantContext(jwtAuth, exchange)
                                .flatMap(tenantContext -> {
                                    TenantContext.set(tenantContext);
                                    MDC.put("tenantId", tenantContext.tenantId().toString());
                                    MDC.put("userId", tenantContext.userId().toString());

                                    return chain.filter(exchange)
                                            .doFinally(signalType -> TenantContext.clear());
                                });
                    }

                    return chain.filter(exchange);
                })
                .switchIfEmpty(chain.filter(exchange));
    }

    private Mono<TenantContext> extractTenantContext(JwtAuthenticationToken jwtAuth, ServerWebExchange exchange) {
        try {
            Claims claims = (Claims) jwtAuth.getTokenAttributes().get("claims");
            if (claims == null) {
                claims = jwtAuth.getToken().getClaims();
            }

            String tenantIdStr = claims.get("tenant_id", String.class);
            String userIdStr = claims.getSubject();
            @SuppressWarnings("unchecked")
            Set<String> roles = jwtAuth.getAuthorities().stream()
                    .map(authority -> authority.getAuthority())
                    .collect(Collectors.toSet());

            UUID tenantId = UUID.fromString(tenantIdStr);
            UUID userId = UUID.fromString(userIdStr);

            log.debug("Extracted tenant context: tenantId={}, userId={}, roles={}",
                    tenantId, userId, roles);

            return Mono.just(new TenantContext(tenantId, userId, roles));
        } catch (Exception e) {
            log.error("Failed to extract tenant context from JWT", e);
            return Mono.error(new IllegalStateException("Invalid JWT token structure"));
        }
    }
}
