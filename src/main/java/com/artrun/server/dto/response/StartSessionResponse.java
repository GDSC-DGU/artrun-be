package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class StartSessionResponse {
    private String sessionId;
    private String routeId;
    private String status;
    private boolean startAllowed;
    private double startDistanceMeters;
    private String message;
    private LocalDateTime startedAt;
}
