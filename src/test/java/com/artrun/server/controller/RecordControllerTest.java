package com.artrun.server.controller;

import com.artrun.server.dto.response.RecordDetailResponse;
import com.artrun.server.dto.response.RecordResponse;
import com.artrun.server.security.CustomUserDetailsService;
import com.artrun.server.security.JwtTokenProvider;
import com.artrun.server.service.RecordService;
import com.artrun.server.support.WithMockCustomUser;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(RecordController.class)
class RecordControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean RecordService recordService;
    @MockitoBean JwtTokenProvider jwtTokenProvider;
    @MockitoBean CustomUserDetailsService customUserDetailsService;

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/records/save - 저장 성공")
    void saveRecord_success() throws Exception {
        RecordResponse response = RecordResponse.builder()
                .recordId("record-001").totalDistanceMeters(4850.0)
                .totalTimeSeconds(1800).averageSpeed(2.69).build();
        when(recordService.saveRecord(eq("user-1"), any())).thenReturn(response);

        mockMvc.perform(post("/api/v1/records/save").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "sessionId": "session-001",
                                    "gpsPoints": [
                                        {"lat": 37.5665, "lng": 126.978, "timestamp": 1000},
                                        {"lat": 37.5670, "lng": 126.979, "timestamp": 2000}
                                    ],
                                    "totalTimeSeconds": 1800
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.recordId").value("record-001"))
                .andExpect(jsonPath("$.data.totalDistanceMeters").value(4850.0));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("POST /api/v1/records/save - 필수 필드 누락 시 400")
    void saveRecord_missingFields_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/records/save").with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"totalTimeSeconds": 1800}
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    @WithMockCustomUser
    @DisplayName("GET /api/v1/records/{recordId} - 상세 조회")
    void getRecord_success() throws Exception {
        RecordDetailResponse response = RecordDetailResponse.builder()
                .recordId("record-001").routeId("route-001")
                .totalDistanceMeters(4850.0).totalTimeSeconds(1800)
                .actualPolyline(List.of()).plannedPolyline(List.of())
                .createdAt(LocalDateTime.now()).build();
        when(recordService.getRecord("user-1", "record-001")).thenReturn(response);

        mockMvc.perform(get("/api/v1/records/record-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.recordId").value("record-001"))
                .andExpect(jsonPath("$.data.totalDistanceMeters").value(4850.0));
    }

    @Test
    @WithMockCustomUser
    @DisplayName("DELETE /api/v1/records/{recordId} - 삭제 성공")
    void deleteRecord_success() throws Exception {
        doNothing().when(recordService).deleteRecord("user-1", "record-001");

        mockMvc.perform(delete("/api/v1/records/record-001").with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }
}
