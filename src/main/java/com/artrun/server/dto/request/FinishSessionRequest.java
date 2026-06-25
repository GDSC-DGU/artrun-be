package com.artrun.server.dto.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
public class FinishSessionRequest {

    private StartSessionRequest.CurrentPointDto currentPoint;
    private Integer totalTimeSeconds;
    private List<GpsPointDto> gpsPoints;

    @Getter
    @NoArgsConstructor
    public static class GpsPointDto {
        private Double lat;
        private Double lng;
        private Long timestamp;
    }
}
