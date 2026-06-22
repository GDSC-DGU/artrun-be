package com.artrun.server.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class RecordDetailResponse {
    private String recordId;
    private String routeId;
    private List<LatLng> plannedPolyline;
    private List<LatLng> actualPolyline;
    private double totalDistanceMeters;
    private int totalTimeSeconds;
    private double averageSpeed;
    private String imageUrl;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class LatLng {
        private double lat;
        private double lng;
    }
}
