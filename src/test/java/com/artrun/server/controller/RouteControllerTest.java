package com.artrun.server.controller;

import com.artrun.server.dto.response.RouteStatusResponse;
import com.artrun.server.dto.response.TaskResponse;
import com.artrun.server.service.RouteService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(RouteController.class)
class RouteControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private RouteService routeService;

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/routes/generate - 202 반환")
    void generateRoute_returns202() throws Exception {
        TaskResponse taskResponse = TaskResponse.builder()
                .taskId("task-1234")
                .message("경로 생성을 시작합니다.")
                .build();
        when(routeService.generateRoute(any())).thenReturn(taskResponse);

        String body = """
                {
                    "requestText": "강아지 모양으로 5km 뛰고 싶어",
                    "shapeType": "dog",
                    "targetDistanceKm": 5.0,
                    "startPoint": {"lat": 37.5665, "lng": 126.978}
                }
                """;

        mockMvc.perform(post("/api/v1/routes/generate")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.taskId").value("task-1234"));
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/routes/generate - 필수 필드 누락 시 400")
    void generateRoute_missingFields_returns400() throws Exception {
        String body = """
                {
                    "shapeType": "dog"
                }
                """;

        mockMvc.perform(post("/api/v1/routes/generate")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @WithMockUser
    @DisplayName("GET /api/v1/routes/status/{taskId} - 완료 상태 조회")
    void getStatus_completed() throws Exception {
        RouteStatusResponse response = RouteStatusResponse.builder()
                .status("COMPLETED")
                .candidateRoutes(List.of(
                        RouteStatusResponse.CandidateRouteDto.builder()
                                .routeId("R_001")
                                .distance(4850.0)
                                .similarityScore(92.0)
                                .polyline(List.of())
                                .build()
                ))
                .build();
        when(routeService.getTaskStatus("task-1234")).thenReturn(response);

        mockMvc.perform(get("/api/v1/routes/status/task-1234"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("COMPLETED"))
                .andExpect(jsonPath("$.data.candidateRoutes[0].routeId").value("R_001"));
    }
}
