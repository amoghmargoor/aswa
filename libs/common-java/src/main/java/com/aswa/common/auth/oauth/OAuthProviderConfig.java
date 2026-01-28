package com.aswa.common.auth.oauth;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * OAuth provider configuration.
 */
@Component
@ConfigurationProperties(prefix = "oauth")
public class OAuthProviderConfig {

    private Map<String, ProviderSettings> providers = new HashMap<>();

    public Map<String, ProviderSettings> getProviders() {
        return providers;
    }

    public void setProviders(Map<String, ProviderSettings> providers) {
        this.providers = providers;
    }

    public ProviderSettings getProvider(String name) {
        return providers.get(name);
    }

    public static class ProviderSettings {
        private String clientId;
        private String clientSecret;
        private String authorizationUri;
        private String tokenUri;
        private String userInfoUri;
        private String jwksUri;
        private String issuer;
        private String[] scopes;
        private String userNameAttribute;
        private String emailAttribute;
        private boolean enabled;

        public String getClientId() { return clientId; }
        public void setClientId(String clientId) { this.clientId = clientId; }

        public String getClientSecret() { return clientSecret; }
        public void setClientSecret(String clientSecret) { this.clientSecret = clientSecret; }

        public String getAuthorizationUri() { return authorizationUri; }
        public void setAuthorizationUri(String authorizationUri) { this.authorizationUri = authorizationUri; }

        public String getTokenUri() { return tokenUri; }
        public void setTokenUri(String tokenUri) { this.tokenUri = tokenUri; }

        public String getUserInfoUri() { return userInfoUri; }
        public void setUserInfoUri(String userInfoUri) { this.userInfoUri = userInfoUri; }

        public String getJwksUri() { return jwksUri; }
        public void setJwksUri(String jwksUri) { this.jwksUri = jwksUri; }

        public String getIssuer() { return issuer; }
        public void setIssuer(String issuer) { this.issuer = issuer; }

        public String[] getScopes() { return scopes; }
        public void setScopes(String[] scopes) { this.scopes = scopes; }

        public String getUserNameAttribute() { return userNameAttribute; }
        public void setUserNameAttribute(String userNameAttribute) { this.userNameAttribute = userNameAttribute; }

        public String getEmailAttribute() { return emailAttribute; }
        public void setEmailAttribute(String emailAttribute) { this.emailAttribute = emailAttribute; }

        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
    }
}
