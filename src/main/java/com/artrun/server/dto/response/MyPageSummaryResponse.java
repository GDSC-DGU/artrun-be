package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class MyPageSummaryResponse {
    private String userId;
    private String nickname;
    private String profileImageUrl;
    private double totalDistanceKm;
    private long totalRunCount;
    private long sharedRouteCount;
    private long likedRouteCount;
}
