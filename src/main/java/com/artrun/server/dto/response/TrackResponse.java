package com.artrun.server.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
public class TrackResponse {
    private boolean onRoute;
    private Double distanceRemaining;
    private Double completionRate;
    private String warningMessage;
}
