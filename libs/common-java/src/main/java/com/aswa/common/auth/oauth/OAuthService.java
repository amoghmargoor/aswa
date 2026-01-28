package com.aswa.common.auth.oauth;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.TokenPair;
import com.aswa.common.auth.JwtTokenProvider;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * OAuth 2.0 / OIDC service for external identity providers.
 */
@Service
public class OAuthService {

    private static final Logger logger = LoggerFactory.getLogger(OAuthService.class);
    private static final SecureRandom secureRandom = new SecureRandom();

    private final OAuthProviderConfig providerConfig;
    private final JwtTokenProvider jwtTokenProvider;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    // State storage (use Redis in production)
    private final Map<String, OAuthState> stateStore = new ConcurrentHashMap<>();

    public OAuthService(
            OAuthProviderConfig providerConfig,
            JwtTokenProvider jwtTokenProvider,
            RestTemplate restTemplate,
            ObjectMapper objectMapper) {
        this.providerConfig = providerConfig;
        this.jwtTokenProvider = jwtTokenProvider;
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
    }

    /**
     * Generate authorization URL for OAuth provider.
     */
    public AuthorizationUrl generateAuthorizationUrl(
            String provider,
            String redirectUri,
            String tenantId) {

        OAuthProviderConfig.ProviderSettings settings = providerConfig.getProvider(provider);
        if (settings == null || !settings.isEnabled()) {
            throw new IllegalArgumentException("OAuth provider not configured: " + provider);
        }

        String state = generateState();
        String nonce = generateNonce();

        // Store state for verification
        stateStore.put(state, new OAuthState(
            provider,
            tenantId,
            redirectUri,
            nonce,
            System.currentTimeMillis() + 600000 // 10 min expiry
        ));

        StringBuilder urlBuilder = new StringBuilder(settings.getAuthorizationUri());
        urlBuilder.append("?response_type=code");
        urlBuilder.append("&client_id=").append(encode(settings.getClientId()));
        urlBuilder.append("&redirect_uri=").append(encode(redirectUri));
        urlBuilder.append("&scope=").append(encode(String.join(" ", settings.getScopes())));
        urlBuilder.append("&state=").append(encode(state));
        urlBuilder.append("&nonce=").append(encode(nonce));

        return new AuthorizationUrl(urlBuilder.toString(), state);
    }

    /**
     * Handle OAuth callback and exchange code for tokens.
     */
    public TokenPair handleCallback(
            String code,
            String state,
            String redirectUri) {

        // Verify state
        OAuthState oauthState = stateStore.remove(state);
        if (oauthState == null) {
            throw new SecurityException("Invalid or expired state");
        }

        if (System.currentTimeMillis() > oauthState.expiresAt()) {
            throw new SecurityException("State expired");
        }

        OAuthProviderConfig.ProviderSettings settings =
            providerConfig.getProvider(oauthState.provider());

        // Exchange code for tokens
        OAuthTokenResponse tokenResponse = exchangeCodeForTokens(
            settings, code, redirectUri
        );

        // Get user info
        UserInfo userInfo = getUserInfo(settings, tokenResponse.accessToken());

        // Create or update user in database (implementation needed)
        UserPrincipal user = createOrUpdateUser(
            oauthState.tenantId(),
            userInfo,
            oauthState.provider()
        );

        // Generate internal tokens
        return jwtTokenProvider.generateTokenPair(user);
    }

    private OAuthTokenResponse exchangeCodeForTokens(
            OAuthProviderConfig.ProviderSettings settings,
            String code,
            String redirectUri) {

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);
        headers.setBasicAuth(settings.getClientId(), settings.getClientSecret());

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("grant_type", "authorization_code");
        body.add("code", code);
        body.add("redirect_uri", redirectUri);

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        ResponseEntity<JsonNode> response = restTemplate.exchange(
            settings.getTokenUri(),
            HttpMethod.POST,
            request,
            JsonNode.class
        );

        JsonNode responseBody = response.getBody();
        return new OAuthTokenResponse(
            responseBody.get("access_token").asText(),
            responseBody.has("id_token") ? responseBody.get("id_token").asText() : null,
            responseBody.has("refresh_token") ? responseBody.get("refresh_token").asText() : null,
            responseBody.get("expires_in").asLong()
        );
    }

    private UserInfo getUserInfo(
            OAuthProviderConfig.ProviderSettings settings,
            String accessToken) {

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(accessToken);

        HttpEntity<Void> request = new HttpEntity<>(headers);

        ResponseEntity<JsonNode> response = restTemplate.exchange(
            settings.getUserInfoUri(),
            HttpMethod.GET,
            request,
            JsonNode.class
        );

        JsonNode userInfoJson = response.getBody();

        String email = userInfoJson.has(settings.getEmailAttribute())
            ? userInfoJson.get(settings.getEmailAttribute()).asText()
            : userInfoJson.get("email").asText();

        String name = userInfoJson.has(settings.getUserNameAttribute())
            ? userInfoJson.get(settings.getUserNameAttribute()).asText()
            : userInfoJson.has("name") ? userInfoJson.get("name").asText() : email;

        String sub = userInfoJson.get("sub").asText();

        return new UserInfo(sub, email, name);
    }

    private UserPrincipal createOrUpdateUser(
            String tenantId,
            UserInfo userInfo,
            String provider) {
        // TODO: Implement user creation/update in database
        // For now, return a basic principal
        return new UserPrincipal(
            UUID.randomUUID().toString(),
            tenantId,
            userInfo.email(),
            userInfo.name(),
            "user",
            List.of()
        );
    }

    private String generateState() {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String generateNonce() {
        byte[] bytes = new byte[16];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    public record AuthorizationUrl(String url, String state) {}
    public record OAuthState(String provider, String tenantId, String redirectUri, String nonce, long expiresAt) {}
    public record OAuthTokenResponse(String accessToken, String idToken, String refreshToken, long expiresIn) {}
    public record UserInfo(String sub, String email, String name) {}
}
