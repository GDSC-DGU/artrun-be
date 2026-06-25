package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class RecordResponse {
    private String recordId;
    private String sessionId;
    private String routeId;
    private String routeName;
    private String shapeType;
    private double totalDistanceMeters;
    private double totalDistanceKm;
    private int totalTimeSeconds;
    private int averagePaceSecPerKm;
    private String averagePaceText;
    private double averageSpeed;
    private int averageBpm;
    private int calories;
    private int matchRate;
    private int completionRate;
    private List<PolylinePoint> correctedPolyline;
    private String imageUrl;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class PolylinePoint {
        private double lat;
        private double lng;
        private int order;
        private Long timestamp;
    }
}
