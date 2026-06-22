package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.AuthProvider;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

@Slf4j
@Service
public class OAuthService {

    private final RestClient restClient;
    private final String kakaoUserInfoUrl;
    private final String googleUserInfoUrl;

    public OAuthService(
            @Value("${oauth.kakao.user-info-url}") String kakaoUserInfoUrl,
            @Value("${oauth.google.user-info-url}") String googleUserInfoUrl) {
        this.restClient = RestClient.create();
        this.kakaoUserInfoUrl = kakaoUserInfoUrl;
        this.googleUserInfoUrl = googleUserInfoUrl;
    }

    public record OAuthUserInfo(String socialId, String email, String nickname, String profileImageUrl) {}

    public OAuthUserInfo getUserInfo(AuthProvider provider, String token) {
        return switch (provider) {
            case KAKAO -> fetchKakaoUserInfo(token);
            case GOOGLE -> fetchGoogleUserInfo(token);
            default -> throw new BusinessException(ErrorCode.OAUTH_FAILED);
        };
    }

    private OAuthUserInfo fetchKakaoUserInfo(String token) {
        try {
            JsonNode body = restClient.get()
                    .uri(kakaoUserInfoUrl)
                    .header("Authorization", "Bearer " + token)
                    .retrieve()
                    .body(JsonNode.class);

            String socialId = body.get("id").asText();
            JsonNode account = body.path("kakao_account");
            String email = account.path("email").asText(null);
            String nickname = account.path("profile").path("nickname").asText("ArtRunner");
            String profileImageUrl = account.path("profile").path("profile_image_url").asText(null);

            return new OAuthUserInfo(socialId, email, nickname, profileImageUrl);
        } catch (Exception e) {
            log.error("Kakao OAuth failed: {}", e.getMessage());
            throw new BusinessException(ErrorCode.OAUTH_FAILED);
        }
    }

    private OAuthUserInfo fetchGoogleUserInfo(String token) {
        try {
            JsonNode body = restClient.get()
                    .uri(googleUserInfoUrl)
                    .header("Authorization", "Bearer " + token)
                    .retrieve()
                    .body(JsonNode.class);

            String socialId = body.get("sub").asText();
            String email = body.path("email").asText(null);
            String nickname = body.path("name").asText("ArtRunner");
            String profileImageUrl = body.path("picture").asText(null);

            return new OAuthUserInfo(socialId, email, nickname, profileImageUrl);
        } catch (Exception e) {
            log.error("Google OAuth failed: {}", e.getMessage());
            throw new BusinessException(ErrorCode.OAUTH_FAILED);
        }
    }
}
