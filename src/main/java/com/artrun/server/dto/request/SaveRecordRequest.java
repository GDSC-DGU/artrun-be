package com.artrun.server.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class SaveRecordRequest {

    @NotBlank(message = "세션 ID를 입력해주세요.")
    private String sessionId;

    private String routeId;

    @NotNull(message = "GPS 데이터를 입력해주세요.")
    private List<GpsPoint> gpsPoints;

    @NotNull(message = "총 운동 시간을 입력해주세요.")
    private Integer totalTimeSeconds;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class GpsPoint {
        private double lat;
        private double lng;
        private long timestamp;
    }
}
