package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.AuthProvider;
import com.artrun.server.domain.User;
import com.artrun.server.dto.request.*;
import com.artrun.server.dto.response.AuthResponse;
import com.artrun.server.dto.response.UserResponse;
import com.artrun.server.repository.UserRepository;
import com.artrun.server.security.JwtTokenProvider;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
public class AuthService {

    private static final String REFRESH_KEY_PREFIX = "refresh:";

    private final UserRepository userRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final PasswordEncoder passwordEncoder;
    private final StringRedisTemplate redisTemplate;
    private final OAuthService oAuthService;

    @Transactional
    public AuthResponse signup(SignupRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }
        if (userRepository.existsByNickname(request.getNickname())) {
            throw new BusinessException(ErrorCode.NICKNAME_ALREADY_EXISTS);
        }

        User user = User.builder()
                .email(request.getEmail())
                .password(passwordEncoder.encode(request.getPassword()))
                .nickname(request.getNickname())
                .provider(AuthProvider.EMAIL)
                .build();

        User saved = userRepository.save(user);
        return issueTokens(saved);
    }

    @Transactional(readOnly = true)
    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new BusinessException(ErrorCode.INVALID_CREDENTIALS));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }

        return issueTokens(user);
    }

    @Transactional
    public AuthResponse socialLogin(SocialLoginRequest request) {
        AuthProvider provider = parseProvider(request.getProvider());
        OAuthService.OAuthUserInfo info = oAuthService.getUserInfo(provider, request.getProviderAccessToken());

        boolean[] isNew = {false};
        User user = userRepository.findByProviderAndSocialId(provider, info.socialId())
                .orElseGet(() -> {
                    isNew[0] = true;
                    String nickname = resolveNickname(info.nickname());
                    return userRepository.save(User.builder()
                            .email(info.email())
                            .nickname(nickname)
                            .profileImageUrl(info.profileImageUrl())
                            .provider(provider)
                            .socialId(info.socialId())
                            .build());
                });

        return issueTokens(user, isNew[0]);
    }

    public AuthResponse refresh(TokenRefreshRequest request) {
        String refreshToken = request.getRefreshToken();
        if (!jwtTokenProvider.validateToken(refreshToken)) {
            throw new BusinessException(ErrorCode.INVALID_TOKEN);
        }

        String userId = jwtTokenProvider.extractUserId(refreshToken);
        String stored = redisTemplate.opsForValue().get(REFRESH_KEY_PREFIX + userId);
        if (!refreshToken.equals(stored)) {
            throw new BusinessException(ErrorCode.INVALID_TOKEN);
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        return issueTokens(user);
    }

    public void logout(String userId) {
        redisTemplate.delete(REFRESH_KEY_PREFIX + userId);
    }

    @Transactional
    public void withdraw(String userId) {
        logout(userId);
        userRepository.deleteById(userId);
    }

    private AuthResponse issueTokens(User user) {
        return issueTokens(user, null);
    }

    private AuthResponse issueTokens(User user, Boolean isNewUser) {
        String accessToken = jwtTokenProvider.generateAccessToken(user.getId());
        String refreshToken = jwtTokenProvider.generateRefreshToken(user.getId());

        redisTemplate.opsForValue().set(
                REFRESH_KEY_PREFIX + user.getId(),
                refreshToken,
                jwtTokenProvider.getRefreshTokenExpiration(),
                TimeUnit.MILLISECONDS);

        return AuthResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .isNewUser(isNewUser)
                .user(UserResponse.from(user))
                .build();
    }

    private AuthProvider parseProvider(String provider) {
        try {
            return AuthProvider.valueOf(provider.toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.OAUTH_FAILED);
        }
    }

    private String resolveNickname(String base) {
        String nickname = base;
        int suffix = 1;
        while (userRepository.existsByNickname(nickname)) {
            nickname = base + suffix++;
        }
        return nickname;
    }
}
