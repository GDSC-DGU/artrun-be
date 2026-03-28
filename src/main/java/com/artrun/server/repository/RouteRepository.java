package com.artrun.server.repository;

import com.artrun.server.domain.Route;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface RouteRepository extends JpaRepository<Route, String> {
    List<Route> findByTaskIdOrderByRankingAsc(String taskId);
}
