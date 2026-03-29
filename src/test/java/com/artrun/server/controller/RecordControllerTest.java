package com.artrun.server.controller;

import com.artrun.server.dto.response.RecordResponse;
import com.artrun.server.service.RecordService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(RecordController.class)
class RecordControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private RecordService recordService;

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/records/save - 저장 성공")
    void saveRecord_success() throws Exception {
        RecordResponse response = RecordResponse.builder()
                .recordId("record-001")
                .totalDistanceMeters(4850.0)
                .totalTimeSeconds(1800)
                .averageSpeed(2.69)
                .build();
        when(recordService.saveRecord(any())).thenReturn(response);

        String body = """
                {
                    "sessionId": "session-001",
                    "gpsPoints": [
                        {"lat": 37.5665, "lng": 126.978, "timestamp": 1000},
                        {"lat": 37.5670, "lng": 126.979, "timestamp": 2000}
                    ],
                    "totalTimeSeconds": 1800
                }
                """;

        mockMvc.perform(post("/api/v1/records/save")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.recordId").value("record-001"))
                .andExpect(jsonPath("$.data.totalDistanceMeters").value(4850.0));
    }

    @Test
    @WithMockUser
    @DisplayName("POST /api/v1/records/save - 필수 필드 누락 시 400")
    void saveRecord_missingFields_returns400() throws Exception {
        String body = """
                {"totalTimeSeconds": 1800}
                """;

        mockMvc.perform(post("/api/v1/records/save")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }
}
