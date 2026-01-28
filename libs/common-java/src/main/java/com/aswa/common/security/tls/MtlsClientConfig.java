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
