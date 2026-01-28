package com.aswa.common.security.headers;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;

/**
 * Filter to add security headers to all responses.
 */
@Component
@Order(1)
public class SecurityHeadersFilter implements Filter {

    @Value("${security.headers.hsts.max-age:31536000}")
    private long hstsMaxAge;

    @Value("${security.headers.hsts.include-subdomains:true}")
    private boolean hstsIncludeSubdomains;

    @Value("${security.headers.hsts.preload:true}")
    private boolean hstsPreload;

    @Value("${security.headers.csp:default-src 'self'}")
    private String contentSecurityPolicy;

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletResponse httpResponse = (HttpServletResponse) response;

        // Strict Transport Security
        StringBuilder hsts = new StringBuilder("max-age=").append(hstsMaxAge);
        if (hstsIncludeSubdomains) {
            hsts.append("; includeSubDomains");
        }
        if (hstsPreload) {
            hsts.append("; preload");
        }
        httpResponse.setHeader("Strict-Transport-Security", hsts.toString());

        // Content Security Policy
        httpResponse.setHeader("Content-Security-Policy", contentSecurityPolicy);

        // Prevent MIME type sniffing
        httpResponse.setHeader("X-Content-Type-Options", "nosniff");

        // Prevent clickjacking
        httpResponse.setHeader("X-Frame-Options", "DENY");

        // XSS Protection (legacy, but still useful)
        httpResponse.setHeader("X-XSS-Protection", "1; mode=block");

        // Referrer Policy
        httpResponse.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");

        // Permissions Policy
        httpResponse.setHeader("Permissions-Policy",
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), " +
            "magnetometer=(), microphone=(), payment=(), usb=()");

        // Cache control for sensitive data
        httpResponse.setHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
        httpResponse.setHeader("Pragma", "no-cache");

        chain.doFilter(request, response);
    }
}
