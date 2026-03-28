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

    @NotBlank
    private String sessionId;

    private String routeId;

    @NotNull
    private List<GpsPoint> gpsPoints;

    @NotNull
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
