package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class LikedRouteResponse {
    private String routeId;
    private String title;
    private String shapeType;
    private double distanceKm;
    private String averagePace;
    private String locationName;
    private String creatorNickname;
    private String thumbnailUrl;
    private int likeCount;
    private LocalDateTime likedAt;
}
