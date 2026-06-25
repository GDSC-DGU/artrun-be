package com.artrun.server.repository;

import com.artrun.server.domain.RouteLike;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface RouteLikeRepository extends JpaRepository<RouteLike, String> {
    boolean existsByUser_IdAndCommunityRoute_Id(String userId, String communityRouteId);
    Optional<RouteLike> findByUser_IdAndCommunityRoute_Id(String userId, String communityRouteId);
    Page<RouteLike> findByUser_IdOrderByCreatedAtDesc(String userId, Pageable pageable);
    long countByUser_Id(String userId);
}
