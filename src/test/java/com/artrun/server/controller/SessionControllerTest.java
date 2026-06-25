package com.artrun.server.controller;

import com.artrun.server.dto.response.FinishSessionResponse;
import com.artrun.server.dto.response.PauseSessionResponse;
import com.artrun.server.dto.response.SessionDetailResponse;
import com.artrun.server.dto.response.StartSessionResponse;
import com.artrun.server.dto.response.TrackResponse;
import com.artrun.server.security.CustomUserDetailsService;
import com.artrun.server.security.JwtTokenProvider;
import com.artrun.server.service.SessionService;
import com.artrun.server.service.TrackingService;
import com.artrun.server.support.WithMockCustomUser;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(SessionController.class)
class SessionControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean TrackingService trackingService;
    @MockitoBean SessionService sessionService;
    @MockitoBean JwtTokenProvider jwtTokenProvider;
    @MockitoBean CustomUserDetailsService customUserDetailsService;

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/session/start - 201 반환")
    void startSession_returns201() throws Exception {
        StartSessionResponse response = StartSessionResponse.builder()
                .sessionId("session-001").routeId("route-001")
                .status("RUNNING").startAllowed(true).build();
        when(sessionService.startSession(eq("user-1"), any())).thenReturn(response);

        mockMvc.perform(post("/api/v1/session/start").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"routeId": "route-001", "currentPoint": {"lat": 0.0, "lng": 0.0}}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.sessionId").value("session-001"))
                .andExpect(jsonPath("$.data.status").value("RUNNING"));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/session/{sessionId}/track - 경로 위 위치")
    void track_onRoute() throws Exception {
        TrackResponse response = TrackResponse.builder()
                .onRoute(true).distanceRemainingMeters(2500).completionRate(50).build();
        when(trackingService.checkPosition(eq("session-001"), any())).thenReturn(response);

        mockMvc.perform(post("/api/v1/session/session-001/track").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"lat": 37.5665, "lng": 126.978}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.onRoute").value(true))
                .andExpect(jsonPath("$.data.completionRate").value(50));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/session/{sessionId}/track - 경로 이탈")
    void track_offRoute() throws Exception {
        TrackResponse response = TrackResponse.builder()
                .onRoute(false).distanceRemainingMeters(3000).completionRate(40)
                .warningMessage("경로에서 이탈했습니다. 다시 경로로 돌아와주세요.").build();
        when(trackingService.checkPosition(eq("session-001"), any())).thenReturn(response);

        mockMvc.perform(post("/api/v1/session/session-001/track").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"lat": 37.57, "lng": 126.99}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.onRoute").value(false))
                .andExpect(jsonPath("$.data.warningMessage").exists());
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/session/{sessionId}/pause - 성공")
    void pause_success() throws Exception {
        PauseSessionResponse response = PauseSessionResponse.builder()
                .sessionId("session-001").status("PAUSED").pausedAt(LocalDateTime.now()).build();
        when(sessionService.pauseSession("user-1", "session-001")).thenReturn(response);

        mockMvc.perform(post("/api/v1/session/session-001/pause").with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/session/{sessionId}/finish - COMPLETED 상태 반환")
    void finish_success() throws Exception {
        FinishSessionResponse response = FinishSessionResponse.builder()
                .sessionId("session-001").routeId("route-001")
                .status("COMPLETED").completionRate(100).recordSaveRequired(true)
                .message("러닝 루트를 완주했습니다.").build();
        when(sessionService.finishSession(eq("user-1"), eq("session-001"), any())).thenReturn(response);

        mockMvc.perform(post("/api/v1/session/session-001/finish").with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("COMPLETED"));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("GET /api/v1/session/{sessionId} - 세션 상태 조회")
    void getSession_success() throws Exception {
        SessionDetailResponse response = SessionDetailResponse.builder()
                .sessionId("session-001").routeId("route-001").status("RUNNING").build();
        when(sessionService.getSession("user-1", "session-001")).thenReturn(response);

        mockMvc.perform(get("/api/v1/session/session-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("RUNNING"));
    }
}
