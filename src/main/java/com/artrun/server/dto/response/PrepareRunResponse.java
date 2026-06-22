package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class PrepareRunResponse {
    private String routeId;
    private double distanceToStart;
    private boolean canRun;
}
