package com.artrun.server.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class RouteDetailResponse {
    private String routeId;
    private String routeName;
    private String shapeType;
    private String activityType;
    private Double distanceKm;
    private Integer estimatedTimeSeconds;
    private Integer targetPaceSecPerKm;
    private Double similarityScore;
    private Double pedestrianRoadRatio;
    private Integer expectedBpm;
    private LatLng startPoint;
    private LatLng endPoint;
    private Bounds bounds;
    private List<PolylinePoint> polyline;
    private List<CheckpointDto> checkpoints;
    private List<TurnInstructionDto> turnInstructions;
    private String previewImageUrl;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class LatLng {
        private double lat;
        private double lng;
    }

    @Getter
    @Builder
    public static class Bounds {
        private LatLng northEast;
        private LatLng southWest;
    }

    @Getter
    @Builder
    public static class PolylinePoint {
        private double lat;
        private double lng;
        private int order;
    }

    @Getter
    @Builder
    public static class CheckpointDto {
        private String checkpointId;
        private int sequence;
        private String name;
        private String description;
        private int distanceFromStartMeters;
        private LatLng point;
    }

    @Getter
    @Builder
    public static class TurnInstructionDto {
        private String instructionId;
        private int sequence;
        private String type;
        private String message;
        private int distanceFromStartMeters;
        private int nextDistanceMeters;
        private LatLng point;
    }
}
