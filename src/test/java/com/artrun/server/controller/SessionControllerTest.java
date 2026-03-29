package com.artrun.server.controller;

import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.dto.response.TrackResponse;
import com.artrun.server.service.SessionService;
import com.artrun.server.service.TrackingService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(SessionController.class)
class SessionControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private TrackingService trackingService;

    @MockitoBean
    private SessionService sessionService;

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/session/start - 201 반환")
    void startSession_returns201() throws Exception {
        SessionResponse response = SessionResponse.builder()
                .sessionId("session-001")
                .routeId("route-001")
                .status("ACTIVE")
                .message("러닝 세션이 시작되었습니다.")
                .build();
        when(sessionService.startSession(any())).thenReturn(response);

        String body = """
                {"routeId": "route-001"}
                """;

        mockMvc.perform(post("/api/v1/session/start")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.sessionId").value("session-001"))
                .andExpect(jsonPath("$.data.status").value("ACTIVE"));
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/session/{sessionId}/track - 경로 위 위치")
    void track_onRoute() throws Exception {
        TrackResponse response = TrackResponse.builder()
                .onRoute(true)
                .distanceRemaining(2500.0)
                .completionRate(50.0)
                .build();
        when(trackingService.checkPosition(eq("session-001"), eq(37.5665), eq(126.978)))
                .thenReturn(response);

        String body = """
                {"lat": 37.5665, "lng": 126.978}
                """;

        mockMvc.perform(post("/api/v1/session/session-001/track")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.onRoute").value(true))
                .andExpect(jsonPath("$.data.completionRate").value(50.0));
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/session/{sessionId}/track - 경로 이탈")
    void track_offRoute() throws Exception {
        TrackResponse response = TrackResponse.builder()
                .onRoute(false)
                .distanceRemaining(3000.0)
                .completionRate(40.0)
                .warningMessage("경로에서 이탈했습니다. 다시 경로로 돌아와주세요.")
                .build();
        when(trackingService.checkPosition(eq("session-001"), eq(37.57), eq(126.99)))
                .thenReturn(response);

        String body = """
                {"lat": 37.57, "lng": 126.99}
                """;

        mockMvc.perform(post("/api/v1/session/session-001/track")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.onRoute").value(false))
                .andExpect(jsonPath("$.data.warningMessage").exists());
    }
}
