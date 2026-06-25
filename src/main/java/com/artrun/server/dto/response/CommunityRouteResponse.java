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
    private String routeId;
    private String recordId;
    private String title;
    private String description;
    private String shapeType;
    private String activityType;
    private Double distanceKm;
    private String averagePaceText;
    private Integer totalTimeSeconds;
    private Integer averageBpm;
    private Integer matchRate;
    private String locationName;
    private String thumbnailUrl;
    private String imageUrl;
    private int likeCount;
    private Boolean liked;
    private CreatorDto creator;
    private RouteDetailDto route;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class CreatorDto {
        private String userId;
        private String nickname;
        private String profileImageUrl;
    }

    @Getter
    @Builder
    public static class RouteDetailDto {
        private String routeId;
        private String routeName;
        private LatLngDto startPoint;
        private LatLngDto endPoint;
        private BoundsDto bounds;
        private List<PolylinePointDto> polyline;
        private List<Object> checkpoints;
        private List<Object> turnInstructions;
    }

    @Getter
    @Builder
    public static class LatLngDto {
        private double lat;
        private double lng;
    }

    @Getter
    @Builder
    public static class BoundsDto {
        private LatLngDto northEast;
        private LatLngDto southWest;
    }

    @Getter
    @Builder
    public static class PolylinePointDto {
        private double lat;
        private double lng;
        private int order;
    }
}
