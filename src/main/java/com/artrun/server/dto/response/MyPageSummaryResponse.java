package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class MyPageSummaryResponse {
    private UserResponse user;
    private long totalRuns;
    private double totalDistanceKm;
    private long totalTimeSeconds;
    private double averagePaceMinPerKm;
}
