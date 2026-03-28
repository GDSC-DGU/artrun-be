package com.artrun.server.service;

import com.artrun.server.domain.TaskStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Slf4j @Service @RequiredArgsConstructor
public class RouteGenerationOrchestrator {
    private final TaskService taskService;

    @Async("routeGenerationExecutor")
    public void executeAsync(String taskId) {
        log.info("Starting async route generation for task: {}", taskId);
        try {
            taskService.updateStatus(taskId, TaskStatus.PROCESSING);
            // Pipeline: Shape Engine → Scale → Match → Route → Validate
            taskService.updateStatus(taskId, TaskStatus.COMPLETED);
            log.info("Route generation completed for task: {}", taskId);
        } catch (Exception e) {
            log.error("Route generation failed for task: {}", taskId, e);
            taskService.markFailed(taskId, e.getMessage());
        }
    }
}
