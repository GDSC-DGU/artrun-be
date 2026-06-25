package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class LikedRouteListResponse {
    private long totalCount;
    private List<LikedRouteResponse> routes;
}
