package com.artrun.server.repository;

import com.artrun.server.domain.RouteTask;
import com.artrun.server.domain.TaskStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.List;

public interface RouteTaskRepository extends JpaRepository<RouteTask, String> {
    List<RouteTask> findByStatusInAndCreatedAtBefore(List<TaskStatus> statuses, LocalDateTime threshold);
}
