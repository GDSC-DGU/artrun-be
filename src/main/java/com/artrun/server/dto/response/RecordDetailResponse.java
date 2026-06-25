package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class RecordDetailResponse {
    private String recordId;
    private String sessionId;
    private String routeId;
    private String routeName;
    private String shapeType;
    private double totalDistanceKm;
    private int totalTimeSeconds;
    private int averagePaceSecPerKm;
    private String averagePaceText;
    private double averageSpeed;
    private int averageBpm;
    private int calories;
    private int matchRate;
    private int completionRate;
    private List<TargetRoutePoint> targetRoutePolyline;
    private List<ActualGpsPoint> actualGpsPoints;
    private List<CorrectedPolylinePoint> correctedPolyline;
    private String imageUrl;
    private boolean communityShared;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class TargetRoutePoint {
        private double lat;
        private double lng;
        private int order;
    }

    @Getter
    @Builder
    public static class ActualGpsPoint {
        private double lat;
        private double lng;
        private Long timestamp;
        private Double accuracyMeters;
        private Double speed;
    }

    @Getter
    @Builder
    public static class CorrectedPolylinePoint {
        private double lat;
        private double lng;
        private int order;
        private Long timestamp;
    }
}
