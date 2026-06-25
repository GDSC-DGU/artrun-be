package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class RecordSummaryResponse {
    private String recordId;
    private String routeId;
    private String routeName;
    private String shapeType;
    private double distanceKm;
    private String averagePace;
    private int totalTimeSeconds;
    private int matchRate;
    private String imageUrl;
    private boolean shared;
    private LocalDateTime completedAt;
}
