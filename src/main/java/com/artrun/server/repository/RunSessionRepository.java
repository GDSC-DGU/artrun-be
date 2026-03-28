package com.artrun.server.repository;

import com.artrun.server.domain.RunSession;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RunSessionRepository extends JpaRepository<RunSession, String> {
}
