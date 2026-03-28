package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.RouteTask;
import com.artrun.server.domain.TaskStatus;
import com.artrun.server.repository.RouteTaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDateTime;

@Slf4j @Service @RequiredArgsConstructor
public class TaskService {
    private final RouteTaskRepository routeTaskRepository;
    @Transactional
    public RouteTask createTask(RouteTask task) { task.setStatus(TaskStatus.PENDING); return routeTaskRepository.save(task); }
    @Transactional(readOnly = true)
    public RouteTask getTask(String taskId) { return routeTaskRepository.findById(taskId).orElseThrow(() -> new BusinessException(ErrorCode.TASK_NOT_FOUND)); }
    @Transactional
    public void updateStatus(String taskId, TaskStatus status) { RouteTask task = getTask(taskId); task.setStatus(status); if (status == TaskStatus.COMPLETED || status == TaskStatus.FAILED) task.setCompletedAt(LocalDateTime.now()); routeTaskRepository.save(task); }
    @Transactional
    public void markFailed(String taskId, String errorMessage) { RouteTask task = getTask(taskId); task.setStatus(TaskStatus.FAILED); task.setErrorMessage(errorMessage); task.setCompletedAt(LocalDateTime.now()); routeTaskRepository.save(task); }
}
