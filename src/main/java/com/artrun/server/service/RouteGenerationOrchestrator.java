package com.artrun.server.service;

import com.artrun.server.domain.TaskStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class RouteGenerationOrchestrator {

    private final TaskService taskService;

    @Async("routeGenerationExecutor")
    public void executeAsync(String taskId) {
        log.info("Starting async route generation for task: {}", taskId);
        try {
            taskService.updateStatus(taskId, TaskStatus.PROCESSING);

            // Pipeline steps (implemented in issues #6-#10):
            // 1. Shape Engine - AI로 anchorPoints 생성
            // 2. Geospatial Scale - 좌표 변환 및 스케일링
            // 3. Map Matching - OSM 노드 스냅
            // 4. Routing Engine - pgRouting 경로 연결
            // 5. Validation & Scoring - 검증 및 점수 산정

            taskService.updateStatus(taskId, TaskStatus.COMPLETED);
            log.info("Route generation completed for task: {}", taskId);
        } catch (Exception e) {
            log.error("Route generation failed for task: {}", taskId, e);
            taskService.markFailed(taskId, e.getMessage());
        }
    }
}
