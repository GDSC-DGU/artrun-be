package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class PrepareRunResponse {
    private String communityRouteId;
    private String routeId;
    private boolean runnable;
    private double startDistanceMeters;
    private String message;
}
