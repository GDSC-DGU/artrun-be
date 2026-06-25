package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.AuthProvider;
import com.artrun.server.domain.User;
import com.artrun.server.dto.request.LoginRequest;
import com.artrun.server.dto.request.SignupRequest;
import com.artrun.server.dto.request.TokenRefreshRequest;
import com.artrun.server.dto.response.AuthResponse;
import com.artrun.server.repository.UserRepository;
import com.artrun.server.security.JwtTokenProvider;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock UserRepository userRepository;
    @Mock JwtTokenProvider jwtTokenProvider;
    @Mock PasswordEncoder passwordEncoder;
    @Mock StringRedisTemplate redisTemplate;
    @Mock OAuthService oAuthService;
    @Mock ValueOperations<String, String> valueOperations;

    @InjectMocks AuthService authService;

    private void mockRedis() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        doNothing().when(valueOperations).set(any(), any(), anyLong(), any());
    }

    @Test
    @DisplayName("정상 회원가입 시 토큰을 반환한다")
    void signup_success() {
        mockRedis();
        when(userRepository.existsByEmail("test@test.com")).thenReturn(false);
        when(userRepository.existsByNickname("테스터")).thenReturn(false);
        when(passwordEncoder.encode(any())).thenReturn("encoded");
        User saved = User.builder().id("user-1").email("test@test.com")
                .nickname("테스터").provider(AuthProvider.EMAIL).build();
        when(userRepository.save(any())).thenReturn(saved);
        when(jwtTokenProvider.generateAccessToken("user-1")).thenReturn("access");
        when(jwtTokenProvider.generateRefreshToken("user-1")).thenReturn("refresh");

        SignupRequest req = new SignupRequest();
        setField(req, "email", "test@test.com");
        setField(req, "password", "password123");
        setField(req, "nickname", "테스터");

        AuthResponse response = authService.signup(req);

        assertThat(response.getAccessToken()).isEqualTo("access");
        assertThat(response.getUser().getUserId()).isEqualTo("user-1");
    }

    @Test
    @DisplayName("중복 이메일로 가입하면 예외를 던진다")
    void signup_duplicateEmail() {
        when(userRepository.existsByEmail("dup@test.com")).thenReturn(true);

        SignupRequest req = new SignupRequest();
        setField(req, "email", "dup@test.com");
        setField(req, "password", "password123");
        setField(req, "nickname", "테스터");

        assertThatThrownBy(() -> authService.signup(req))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.EMAIL_ALREADY_EXISTS);
    }

    @Test
    @DisplayName("올바른 이메일/비밀번호로 로그인 성공")
    void login_success() {
        mockRedis();
        User user = User.builder().id("user-1").email("test@test.com")
                .password("encoded").nickname("테스터").provider(AuthProvider.EMAIL).build();

        when(userRepository.findByEmail("test@test.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("password123", "encoded")).thenReturn(true);
        when(jwtTokenProvider.generateAccessToken("user-1")).thenReturn("access");
        when(jwtTokenProvider.generateRefreshToken("user-1")).thenReturn("refresh");

        LoginRequest req = new LoginRequest();
        setField(req, "email", "test@test.com");
        setField(req, "password", "password123");

        AuthResponse response = authService.login(req);

        assertThat(response.getAccessToken()).isEqualTo("access");
    }

    @Test
    @DisplayName("틀린 비밀번호로 로그인하면 예외를 던진다")
    void login_wrongPassword() {
        User user = User.builder().id("user-1").email("test@test.com")
                .password("encoded").nickname("테스터").provider(AuthProvider.EMAIL).build();

        when(userRepository.findByEmail("test@test.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("wrong", "encoded")).thenReturn(false);

        LoginRequest req = new LoginRequest();
        setField(req, "email", "test@test.com");
        setField(req, "password", "wrong");

        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_CREDENTIALS);
    }

    @Test
    @DisplayName("유효한 refresh token으로 재발급 성공")
    void refresh_success() {
        mockRedis();
        when(jwtTokenProvider.validateToken("valid-refresh")).thenReturn(true);
        when(jwtTokenProvider.extractUserId("valid-refresh")).thenReturn("user-1");
        when(valueOperations.get("refresh:user-1")).thenReturn("valid-refresh");

        User user = User.builder().id("user-1").email("test@test.com")
                .nickname("테스터").provider(AuthProvider.EMAIL).build();
        when(userRepository.findById("user-1")).thenReturn(Optional.of(user));
        when(jwtTokenProvider.generateAccessToken("user-1")).thenReturn("new-access");
        when(jwtTokenProvider.generateRefreshToken("user-1")).thenReturn("new-refresh");

        TokenRefreshRequest req = new TokenRefreshRequest();
        setField(req, "refreshToken", "valid-refresh");

        AuthResponse response = authService.refresh(req);

        assertThat(response.getAccessToken()).isEqualTo("new-access");
    }

    @Test
    @DisplayName("Redis에 저장된 토큰과 다르면 예외를 던진다")
    void refresh_tokenMismatch() {
        when(jwtTokenProvider.validateToken("tampered")).thenReturn(true);
        when(jwtTokenProvider.extractUserId("tampered")).thenReturn("user-1");
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("refresh:user-1")).thenReturn("original-refresh");

        TokenRefreshRequest req = new TokenRefreshRequest();
        setField(req, "refreshToken", "tampered");

        assertThatThrownBy(() -> authService.refresh(req))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_TOKEN);
    }

    @Test
    @DisplayName("로그아웃 시 Redis에서 refresh token을 삭제한다")
    void logout_deletesRefreshToken() {
        authService.logout("user-1");
        verify(redisTemplate).delete("refresh:user-1");
    }

    // reflection 없이 DTO 필드 세팅 (테스트 전용)
    private void setField(Object obj, String name, String value) {
        try {
            var field = obj.getClass().getDeclaredField(name);
            field.setAccessible(true);
            field.set(obj, value);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
