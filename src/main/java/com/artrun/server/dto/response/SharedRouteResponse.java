package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class SharedRouteResponse {
    private String communityRouteId;
    private String recordId;
    private String routeId;
    private String title;
    private String description;
    private double distanceKm;
    private String imageUrl;
    private int likeCount;
    private LocalDateTime createdAt;
}
