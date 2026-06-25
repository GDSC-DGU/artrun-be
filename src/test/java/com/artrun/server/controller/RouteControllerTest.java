package com.artrun.server.controller;

import com.artrun.server.dto.response.RouteDetailResponse;
import com.artrun.server.dto.response.RouteStatusResponse;
import com.artrun.server.dto.response.TaskResponse;
import com.artrun.server.security.CustomUserDetailsService;
import com.artrun.server.security.JwtTokenProvider;
import com.artrun.server.service.RouteService;
import com.artrun.server.support.WithMockCustomUser;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(RouteController.class)
class RouteControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean RouteService routeService;
    @MockitoBean JwtTokenProvider jwtTokenProvider;
    @MockitoBean CustomUserDetailsService customUserDetailsService;

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/routes/generate - 202 반환")
    void generateRoute_returns202() throws Exception {
        when(routeService.generateRoute(any())).thenReturn(
                TaskResponse.builder().taskId("task-1234").status("PENDING").build());

        mockMvc.perform(post("/api/v1/routes/generate").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "requestText": "별 모양 5km",
                                    "shapeType": "STAR",
                                    "targetDistanceKm": 5.0,
                                    "startPoint": {"lat": 37.5665, "lng": 126.978}
                                }
                                """))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.data.taskId").value("task-1234"));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/routes/generate - 필수 필드 누락 시 400")
    void generateRoute_missingFields_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/routes/generate").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"shapeType": "STAR"}
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    @WithMockCustomUser
    @DisplayName("GET /api/v1/routes/status/{taskId} - 완료 상태 조회")
    void getStatus_completed() throws Exception {
        when(routeService.getTaskStatus("task-1234")).thenReturn(
                RouteStatusResponse.builder()
                        .status("COMPLETED")
                        .candidateRoutes(List.of(
                                RouteStatusResponse.CandidateRouteDto.builder()
                                        .routeId("R_001").distanceKm(4.85)
                                        .similarityScore(92.0).polyline(List.of()).build()))
                        .build());

        mockMvc.perform(get("/api/v1/routes/status/task-1234"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("COMPLETED"))
                .andExpect(jsonPath("$.data.candidateRoutes[0].routeId").value("R_001"));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("GET /api/v1/routes/{routeId} - 루트 상세 조회")
    void getRoute_success() throws Exception {
        when(routeService.getRoute("route-001")).thenReturn(
                RouteDetailResponse.builder()
                        .routeId("route-001").distanceKm(5.0)
                        .polyline(List.of()).checkpoints(List.of()).build());

        mockMvc.perform(get("/api/v1/routes/route-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.routeId").value("route-001"))
                .andExpect(jsonPath("$.data.distanceKm").value(5.0));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/routes/{routeId}/regenerate - 202 반환")
    void regenerateRoute_returns202() throws Exception {
        when(routeService.regenerateRoute(eq("route-001"), any())).thenReturn(
                TaskResponse.builder().taskId("task-new").status("PENDING").build());

        mockMvc.perform(post("/api/v1/routes/route-001/regenerate").with(csrf()))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.data.taskId").value("task-new"));
    }
}
