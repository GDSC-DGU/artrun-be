package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class FinishSessionResponse {
    private String sessionId;
    private String routeId;
    private String status;
    private int completionRate;
    private boolean recordSaveRequired;
    private String message;
}
