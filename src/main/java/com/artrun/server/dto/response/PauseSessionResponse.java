package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class PauseSessionResponse {
    private String sessionId;
    private String status;
    private LocalDateTime pausedAt;
}
