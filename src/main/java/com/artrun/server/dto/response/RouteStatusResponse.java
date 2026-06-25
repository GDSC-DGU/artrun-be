package com.artrun.server.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class RouteStatusResponse {
    private String status;
    private Integer progressRate;
    private String errorMessage;
    private List<CandidateRouteDto> candidateRoutes;

    @Getter
    @Builder
    @AllArgsConstructor
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class CandidateRouteDto {
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
        private RouteDetailResponse.LatLng startPoint;
        private RouteDetailResponse.LatLng endPoint;
        private RouteDetailResponse.Bounds bounds;
        private List<RouteDetailResponse.PolylinePoint> polyline;
        private List<RouteDetailResponse.CheckpointDto> checkpoints;
        private List<RouteDetailResponse.TurnInstructionDto> turnInstructions;
        private String previewImageUrl;
        private List<String> warnings;
    }
}
