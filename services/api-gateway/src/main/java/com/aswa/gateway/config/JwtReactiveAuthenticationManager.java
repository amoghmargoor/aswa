package com.aswa.gateway.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.ReactiveAuthenticationManager;
import org.springframework.security.core.Authentication;
import reactor.core.publisher.Mono;

/**
 * JWT Reactive Authentication Manager.
 *
 * This manager accepts pre-authenticated JWT tokens and validates them.
 * The actual token validation happens in JwtAuthenticationConverter.
 */
@Slf4j
public class JwtReactiveAuthenticationManager implements ReactiveAuthenticationManager {

    @Override
    public Mono<Authentication> authenticate(Authentication authentication) {
        // Token is already validated in JwtAuthenticationConverter
        // If we reach here, the token is valid
        log.debug("Authenticating user: {}", authentication.getName());
        return Mono.just(authentication);
    }
}
