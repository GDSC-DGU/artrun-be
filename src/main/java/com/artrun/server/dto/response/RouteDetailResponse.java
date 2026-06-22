package com.artrun.server.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class RouteDetailResponse {
    private String routeId;
    private double distanceMeters;
    private Double similarityScore;
    private Double pedestrianRoadRatio;
    private List<LatLng> polyline;
    private List<LatLng> checkpoints;

    @Getter
    @Builder
    public static class LatLng {
        private double lat;
        private double lng;
    }
}
