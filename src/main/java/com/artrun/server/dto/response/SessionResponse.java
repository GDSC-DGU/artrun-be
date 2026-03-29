package com.artrun.server.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
public class SessionResponse {
    private String sessionId;
    private String routeId;
    private String status;
    private String message;
}
