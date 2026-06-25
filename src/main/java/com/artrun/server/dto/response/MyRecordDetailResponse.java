package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class MyRecordDetailResponse {
    private String recordId;
    private String routeId;
    private String routeName;
    private String shapeType;
    private double distanceKm;
    private String averagePace;
    private int averageBpm;
    private int totalTimeSeconds;
    private int matchRate;
    private String imageUrl;
    private boolean shared;
    private List<LatLng> routePolyline;
    private List<GpsPoint> actualGpsPoints;
    private LocalDateTime completedAt;

    @Getter
    @Builder
    public static class LatLng {
        private double lat;
        private double lng;
    }

    @Getter
    @Builder
    public static class GpsPoint {
        private double lat;
        private double lng;
        private Long timestamp;
    }
}
