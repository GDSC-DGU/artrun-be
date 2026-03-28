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
    private String errorMessage;
    private List<CandidateRouteDto> candidateRoutes;

    @Getter
    @Builder
    @AllArgsConstructor
    public static class CandidateRouteDto {
        private String routeId;
        private Double distance;
        private Double similarityScore;
        private Double pedestrianRoadRatio;
        private List<LatLng> polyline;
    }

    @Getter
    @AllArgsConstructor
    public static class LatLng {
        private double lat;
        private double lng;
    }
}
