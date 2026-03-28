package com.artrun.server.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
public class TaskResponse {
    private String taskId;
    private String message;
}
