package com.artrun.server.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class SessionDetailResponse {
    private String sessionId;
    private String routeId;
    private String status;
    private LocalDateTime startedAt;
    private LocalDateTime finishedAt;
}
