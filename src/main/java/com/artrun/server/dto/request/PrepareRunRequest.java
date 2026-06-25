package com.artrun.server.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class PrepareRunRequest {

    @Valid
    @NotNull(message = "현재 위치 정보를 입력해주세요.")
    private CurrentPointDto currentPoint;

    @Getter
    @NoArgsConstructor
    public static class CurrentPointDto {
        @NotNull private Double lat;
        @NotNull private Double lng;
        private Double accuracyMeters;
        private Long timestamp;
    }
}
