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
