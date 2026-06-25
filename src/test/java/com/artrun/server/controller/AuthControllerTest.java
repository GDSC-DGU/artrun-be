package com.artrun.server.controller;

import com.artrun.server.domain.AuthProvider;
import com.artrun.server.domain.User;
import com.artrun.server.dto.response.AuthResponse;
import com.artrun.server.dto.response.UserResponse;
import com.artrun.server.security.CustomUserDetailsService;
import com.artrun.server.security.JwtTokenProvider;
import com.artrun.server.service.AuthService;
import com.artrun.server.support.WithMockCustomUser;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(AuthController.class)
class AuthControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean AuthService authService;
    @MockitoBean JwtTokenProvider jwtTokenProvider;
    @MockitoBean CustomUserDetailsService customUserDetailsService;

    private AuthResponse mockAuthResponse() {
        User user = User.builder().id("user-1").email("test@test.com")
                .nickname("테스터").provider(AuthProvider.EMAIL).build();
        return AuthResponse.builder()
                .accessToken("access-token").refreshToken("refresh-token")
                .user(UserResponse.from(user)).build();
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/auth/signup - 회원가입 성공 시 201 반환")
    void signup_success() throws Exception {
        when(authService.signup(any())).thenReturn(mockAuthResponse());

        mockMvc.perform(post("/api/v1/auth/signup").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "email": "test@test.com",
                                    "password": "password123",
                                    "nickname": "테스터"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.accessToken").value("access-token"))
                .andExpect(jsonPath("$.data.user.email").value("test@test.com"));
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/auth/signup - 이메일 형식 오류 시 400")
    void signup_invalidEmail_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/auth/signup").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "email": "not-an-email",
                                    "password": "password123",
                                    "nickname": "테스터"
                                }
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/auth/signup - 비밀번호 8자 미만 시 400")
    void signup_shortPassword_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/auth/signup").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "email": "test@test.com",
                                    "password": "short",
                                    "nickname": "테스터"
                                }
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/auth/login - 로그인 성공")
    void login_success() throws Exception {
        when(authService.login(any())).thenReturn(mockAuthResponse());

        mockMvc.perform(post("/api/v1/auth/login").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "email": "test@test.com",
                                    "password": "password123"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.accessToken").value("access-token"));
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/auth/social-login - 카카오 로그인")
    void socialLogin_kakao() throws Exception {
        when(authService.socialLogin(any())).thenReturn(mockAuthResponse());

        mockMvc.perform(post("/api/v1/auth/social-login").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "provider": "KAKAO",
                                    "providerAccessToken": "kakao-access-token"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.accessToken").value("access-token"));
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/auth/refresh - 토큰 재발급")
    void refresh_success() throws Exception {
        when(authService.refresh(any())).thenReturn(mockAuthResponse());

        mockMvc.perform(post("/api/v1/auth/refresh").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"refreshToken": "old-refresh-token"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.accessToken").value("access-token"));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/auth/logout - 로그아웃 성공")
    void logout_success() throws Exception {
        doNothing().when(authService).logout("user-1");

        mockMvc.perform(post("/api/v1/auth/logout").with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/auth/withdraw - 회원탈퇴 성공")
    void withdraw_success() throws Exception {
        doNothing().when(authService).withdraw("user-1");

        mockMvc.perform(post("/api/v1/auth/withdraw").with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }
}
