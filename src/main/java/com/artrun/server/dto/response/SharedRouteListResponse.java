package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class SharedRouteListResponse {
    private long totalCount;
    private List<SharedRouteResponse> routes;
}
