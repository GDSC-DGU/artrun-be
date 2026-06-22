package com.artrun.server.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class CommunityRouteResponse {
    private String communityRouteId;
    private String title;
    private String description;
    private UserResponse author;
    private String routeId;
    private List<LatLng> polyline;
    private double distanceMeters;
    private int totalTimeSeconds;
    private String imageUrl;
    private int likeCount;
    private Boolean liked;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class LatLng {
        private double lat;
        private double lng;
    }
}
