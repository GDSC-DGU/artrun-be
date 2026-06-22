package com.artrun.server.repository;

import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface RunSessionRepository extends JpaRepository<RunSession, String> {
    boolean existsByUser_IdAndRoute_IdAndStatus(String userId, String routeId, SessionStatus status);
    Optional<RunSession> findByIdAndUser_Id(String id, String userId);
}
