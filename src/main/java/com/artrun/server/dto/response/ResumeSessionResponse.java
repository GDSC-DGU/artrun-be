package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class ResumeSessionResponse {
    private String sessionId;
    private String status;
    private LocalDateTime resumedAt;
    private boolean onRoute;
    private int offRouteDistanceMeters;
}
