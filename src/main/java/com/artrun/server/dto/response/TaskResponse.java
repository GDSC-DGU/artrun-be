package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TaskResponse {
    private String taskId;
    private String status;
    private Integer estimatedSeconds;
}
