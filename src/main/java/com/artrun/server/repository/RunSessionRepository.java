package com.artrun.server.repository;

import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RunSessionRepository extends JpaRepository<RunSession, String> {
    boolean existsByRoute_IdAndStatus(String routeId, SessionStatus status);
}
