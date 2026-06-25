package com.artrun.server.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StartSessionRequest {

    @NotBlank(message = "경로 ID를 입력해주세요.")
    private String routeId;

    @NotNull(message = "현재 위치를 입력해주세요.")
    @Valid
    private CurrentPointDto currentPoint;

    private Integer targetPaceSecPerKm;
    private boolean voiceGuideEnabled;
    private boolean edmControlEnabled;

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CurrentPointDto {
        @NotNull private Double lat;
        @NotNull private Double lng;
        private Double accuracyMeters;
        private Long timestamp;
    }
}
