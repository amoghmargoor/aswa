# Task 8.2.2: Data Security - Encryption in Transit

## Context

You are implementing data security for ASWA. Encryption at rest is complete. Now we need encryption in transit (TLS/mTLS).

## Objective

Create encryption in transit implementation that:
1. Enforces TLS 1.3 for all external connections
2. Implements mTLS for service-to-service communication
3. Configures certificate management
4. Implements secure headers
5. Sets up certificate rotation

## Requirements

### 1. Create `/infrastructure/kubernetes/security/tls/certificate-issuer.yaml`
```yaml
# cert-manager ClusterIssuers for TLS certificates

apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: security@aswa.io
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - http01:
          ingress:
            class: nginx
        selector:
          dnsZones:
            - "aswa.io"
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: security@aswa.io
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
      - http01:
          ingress:
            class: nginx
---
# Internal CA for mTLS
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: aswa-internal-ca
spec:
  ca:
    secretName: aswa-internal-ca-keypair
---
# Self-signed issuer for bootstrapping internal CA
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}
---
# Create internal CA certificate
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: aswa-internal-ca
  namespace: cert-manager
spec:
  isCA: true
  commonName: ASWA Internal CA
  secretName: aswa-internal-ca-keypair
  duration: 87600h # 10 years
  renewBefore: 8760h # 1 year
  privateKey:
    algorithm: ECDSA
    size: 384
  issuerRef:
    name: selfsigned-issuer
    kind: ClusterIssuer
```

### 2. Create `/infrastructure/kubernetes/security/tls/service-certificates.yaml`
```yaml
# Service certificates for mTLS

# API Gateway certificate
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-gateway-tls
  namespace: aswa-production
spec:
  secretName: api-gateway-tls
  duration: 720h # 30 days
  renewBefore: 168h # 7 days
  subject:
    organizations:
      - ASWA
  privateKey:
    algorithm: ECDSA
    size: 256
  usages:
    - server auth
    - client auth
  dnsNames:
    - api-gateway
    - api-gateway.aswa-production.svc
    - api-gateway.aswa-production.svc.cluster.local
    - api.aswa.io
  issuerRef:
    name: aswa-internal-ca
    kind: ClusterIssuer
---
# Ingestion Service certificate
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ingestion-service-tls
  namespace: aswa-production
spec:
  secretName: ingestion-service-tls
  duration: 720h
  renewBefore: 168h
  subject:
    organizations:
      - ASWA
  privateKey:
    algorithm: ECDSA
    size: 256
  usages:
    - server auth
    - client auth
  dnsNames:
    - ingestion-service
    - ingestion-service.aswa-production.svc
    - ingestion-service.aswa-production.svc.cluster.local
  issuerRef:
    name: aswa-internal-ca
    kind: ClusterIssuer
---
# Query Service certificate
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: query-service-tls
  namespace: aswa-production
spec:
  secretName: query-service-tls
  duration: 720h
  renewBefore: 168h
  subject:
    organizations:
      - ASWA
  privateKey:
    algorithm: ECDSA
    size: 256
  usages:
    - server auth
    - client auth
  dnsNames:
    - query-service
    - query-service.aswa-production.svc
    - query-service.aswa-production.svc.cluster.local
  issuerRef:
    name: aswa-internal-ca
    kind: ClusterIssuer
---
# Insight Service certificate
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: insight-service-tls
  namespace: aswa-production
spec:
  secretName: insight-service-tls
  duration: 720h
  renewBefore: 168h
  subject:
    organizations:
      - ASWA
  privateKey:
    algorithm: ECDSA
    size: 256
  usages:
    - server auth
    - client auth
  dnsNames:
    - insight-service
    - insight-service.aswa-production.svc
    - insight-service.aswa-production.svc.cluster.local
  issuerRef:
    name: aswa-internal-ca
    kind: ClusterIssuer
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/security/tls/TlsConfig.java`
```java
package com.aswa.common.security.tls;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;

import javax.net.ssl.*;
import java.io.IOException;
import java.io.InputStream;
import java.security.*;
import java.security.cert.CertificateException;

/**
 * TLS configuration for secure connections.
 */
@Configuration
public class TlsConfig {

    @Value("${tls.keystore.path:}")
    private Resource keystorePath;

    @Value("${tls.keystore.password:}")
    private String keystorePassword;

    @Value("${tls.truststore.path:}")
    private Resource truststorePath;

    @Value("${tls.truststore.password:}")
    private String truststorePassword;

    @Value("${tls.mtls.enabled:false}")
    private boolean mtlsEnabled;

    @Bean
    public SSLContext sslContext() throws Exception {
        if (keystorePath == null || !keystorePath.exists()) {
            // Return default SSL context for development
            return SSLContext.getDefault();
        }

        KeyStore keyStore = loadKeyStore(keystorePath, keystorePassword);
        KeyStore trustStore = loadKeyStore(truststorePath, truststorePassword);

        KeyManagerFactory kmf = KeyManagerFactory.getInstance(
            KeyManagerFactory.getDefaultAlgorithm()
        );
        kmf.init(keyStore, keystorePassword.toCharArray());

        TrustManagerFactory tmf = TrustManagerFactory.getInstance(
            TrustManagerFactory.getDefaultAlgorithm()
        );
        tmf.init(trustStore);

        SSLContext sslContext = SSLContext.getInstance("TLSv1.3");
        sslContext.init(kmf.getKeyManagers(), tmf.getTrustManagers(), new SecureRandom());

        return sslContext;
    }

    @Bean
    public MtlsClientConfig mtlsClientConfig() throws Exception {
        if (!mtlsEnabled) {
            return MtlsClientConfig.disabled();
        }

        SSLContext sslContext = sslContext();
        return new MtlsClientConfig(sslContext, true);
    }

    private KeyStore loadKeyStore(Resource resource, String password)
            throws KeyStoreException, IOException, NoSuchAlgorithmException, CertificateException {
        KeyStore keyStore = KeyStore.getInstance("PKCS12");
        try (InputStream is = resource.getInputStream()) {
            keyStore.load(is, password.toCharArray());
        }
        return keyStore;
    }
}
```

### 4. Create `/libs/common-java/src/main/java/com/aswa/common/security/tls/MtlsClientConfig.java`
```java
package com.aswa.common.security.tls;

import javax.net.ssl.SSLContext;

/**
 * mTLS client configuration.
 */
public class MtlsClientConfig {

    private final SSLContext sslContext;
    private final boolean enabled;

    public MtlsClientConfig(SSLContext sslContext, boolean enabled) {
        this.sslContext = sslContext;
        this.enabled = enabled;
    }

    public static MtlsClientConfig disabled() {
        return new MtlsClientConfig(null, false);
    }

    public SSLContext getSslContext() {
        return sslContext;
    }

    public boolean isEnabled() {
        return enabled;
    }
}
```

### 5. Create `/libs/common-java/src/main/java/com/aswa/common/security/headers/SecurityHeadersFilter.java`
```java
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
```

### 6. Create `/libs/common-python/src/aswa_common/tls.py`
```python
"""TLS configuration for Python services."""

import os
import ssl
from pathlib import Path
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


class TlsConfig:
    """TLS/mTLS configuration."""

    def __init__(
        self,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        ca_file: Optional[str] = None,
        verify: bool = True,
        mtls_enabled: bool = False,
    ):
        self.cert_file = cert_file or os.environ.get("TLS_CERT_FILE")
        self.key_file = key_file or os.environ.get("TLS_KEY_FILE")
        self.ca_file = ca_file or os.environ.get("TLS_CA_FILE")
        self.verify = verify
        self.mtls_enabled = mtls_enabled or os.environ.get("MTLS_ENABLED", "false").lower() == "true"

    def create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS 1.3."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_3

        # Load CA certificates
        if self.ca_file and Path(self.ca_file).exists():
            context.load_verify_locations(self.ca_file)
        else:
            context.load_default_certs()

        # Load client certificate for mTLS
        if self.mtls_enabled and self.cert_file and self.key_file:
            context.load_cert_chain(self.cert_file, self.key_file)

        context.verify_mode = ssl.CERT_REQUIRED if self.verify else ssl.CERT_NONE
        context.check_hostname = self.verify

        return context

    def get_httpx_client(self, **kwargs) -> httpx.AsyncClient:
        """Create HTTPX client with TLS configuration."""
        if self.mtls_enabled:
            return httpx.AsyncClient(
                cert=(self.cert_file, self.key_file),
                verify=self.ca_file if self.ca_file else True,
                **kwargs,
            )
        return httpx.AsyncClient(verify=self.verify, **kwargs)


def configure_uvicorn_ssl(
    cert_file: str,
    key_file: str,
    ca_file: Optional[str] = None,
    mtls: bool = False,
) -> dict:
    """Configure Uvicorn SSL settings."""
    config = {
        "ssl_certfile": cert_file,
        "ssl_keyfile": key_file,
        "ssl_version": ssl.TLSVersion.TLSv1_3,
    }

    if mtls and ca_file:
        config["ssl_ca_certs"] = ca_file
        config["ssl_cert_reqs"] = ssl.CERT_REQUIRED

    return config


# Security headers middleware for FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    def __init__(
        self,
        app,
        hsts_max_age: int = 31536000,
        csp: str = "default-src 'self'",
    ):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.csp = csp

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["Strict-Transport-Security"] = (
            f"max-age={self.hsts_max_age}; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = self.csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        return response
```

### 7. Create Ingress with TLS configuration

Create `/infrastructure/kubernetes/security/tls/ingress.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: aswa-ingress
  namespace: aswa-production
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-ssl-verify: "on"
    nginx.ingress.kubernetes.io/proxy-ssl-protocols: "TLSv1.3"
    nginx.ingress.kubernetes.io/ssl-protocols: "TLSv1.3"
    nginx.ingress.kubernetes.io/ssl-ciphers: "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384"
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload";
      more_set_headers "X-Content-Type-Options: nosniff";
      more_set_headers "X-Frame-Options: DENY";
      more_set_headers "X-XSS-Protection: 1; mode=block";
spec:
  tls:
    - hosts:
        - api.aswa.io
        - app.aswa.io
      secretName: aswa-tls-cert
  rules:
    - host: api.aswa.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 8000
    - host: app.aswa.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web-dashboard
                port:
                  number: 3000
```

## Test Requirements

Create tests:

1. **TLS connection tests** - Verify TLS 1.3 only
2. **mTLS tests** - Test mutual authentication
3. **Security headers tests** - Verify all headers present
4. **Certificate validation tests** - Test certificate expiry

## Verification

1. Test TLS version: `openssl s_client -connect api.aswa.io:443 -tls1_3`
2. Check security headers: `curl -I https://api.aswa.io`
3. Verify mTLS between services
4. Run SSL Labs scan
5. Verify certificate rotation
