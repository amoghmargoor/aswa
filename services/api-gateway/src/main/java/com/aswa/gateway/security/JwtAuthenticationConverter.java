package com.aswa.gateway.security;

import io.jsonwebtoken.Claims;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.web.server.authentication.ServerAuthenticationConverter;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Converts JWT token from Authorization header into Spring Security Authentication.
 */
@Slf4j
@RequiredArgsConstructor
public class JwtAuthenticationConverter implements ServerAuthenticationConverter {

    private static final String BEARER_PREFIX = "Bearer ";
    private final JwtService jwtService;

    @Override
    public Mono<Authentication> convert(ServerWebExchange exchange) {
        return Mono.justOrEmpty(exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION))
                .filter(header -> header.startsWith(BEARER_PREFIX))
                .map(header -> header.substring(BEARER_PREFIX.length()))
                .flatMap(token -> jwtService.validateToken(token)
                        .map(claims -> createAuthentication(claims, token))
                        .onErrorResume(e -> {
                            log.warn("JWT validation failed: {}", e.getMessage());
                            return Mono.empty();
                        })
                );
    }

    private Authentication createAuthentication(Claims claims, String token) {
        String userId = claims.getSubject();
        String rolesStr = claims.get("roles", String.class);

        List<SimpleGrantedAuthority> authorities = rolesStr != null && !rolesStr.isEmpty()
                ? Arrays.stream(rolesStr.split(","))
                    .map(role -> new SimpleGrantedAuthority("ROLE_" + role.trim().toUpperCase()))
                    .collect(Collectors.toList())
                : Collections.emptyList();

        log.debug("Created authentication for user={} with authorities={}", userId, authorities);

        // Create JWT authentication token with claims in attributes
        return new UsernamePasswordAuthenticationToken(userId, token, authorities);
    }
}
