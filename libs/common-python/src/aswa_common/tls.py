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
