package com.artrun.server.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class RouteGenerateRequest {

    @NotBlank(message = "요청 텍스트를 입력해주세요.")
    private String requestText;

    @NotBlank(message = "도형 유형을 선택해주세요.")
    private String shapeType;

    private String activityType;

    @NotNull(message = "목표 거리를 입력해주세요.")
    @Positive(message = "목표 거리는 양수여야 합니다.")
    private Double targetDistanceKm;

    @NotNull @Valid
    private StartPointDto startPoint;

    private PreferencesDto preferences;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class StartPointDto {
        @NotNull private Double lat;
        @NotNull private Double lng;
    }

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PreferencesDto {
        private boolean avoidMainRoad;
        private boolean preferPark;
    }
}
