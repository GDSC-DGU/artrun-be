package com.artrun.server.service;

import com.artrun.server.domain.RouteTask;
import com.artrun.server.domain.TaskStatus;
import com.artrun.server.repository.RouteTaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class TaskCleanupScheduler {

    private static final int STALE_MINUTES = 30;

    private final RouteTaskRepository routeTaskRepository;

    @Scheduled(fixedDelay = 60_000)
    @Transactional
    public void cleanupStaleTasks() {
        LocalDateTime threshold = LocalDateTime.now().minusMinutes(STALE_MINUTES);
        List<RouteTask> staleTasks = routeTaskRepository.findByStatusInAndCreatedAtBefore(
                List.of(TaskStatus.PENDING, TaskStatus.PROCESSING), threshold);

        for (RouteTask task : staleTasks) {
            task.setStatus(TaskStatus.FAILED);
            task.setErrorMessage("처리 시간 초과로 자동 실패 처리되었습니다.");
            task.setCompletedAt(LocalDateTime.now());
        }

        if (!staleTasks.isEmpty()) {
            log.warn("Cleaned up {} stale tasks (older than {} minutes)", staleTasks.size(), STALE_MINUTES);
        }
    }
}
