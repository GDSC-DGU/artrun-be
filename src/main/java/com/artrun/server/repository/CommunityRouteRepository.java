package com.artrun.server.repository;

import com.artrun.server.domain.CommunityRoute;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CommunityRouteRepository extends JpaRepository<CommunityRoute, String> {
    Page<CommunityRoute> findAllByOrderByCreatedAtDesc(Pageable pageable);
    Page<CommunityRoute> findByUser_IdOrderByCreatedAtDesc(String userId, Pageable pageable);
    boolean existsByRecord_Id(String recordId);

    @Modifying
    @Query("UPDATE CommunityRoute c SET c.likeCount = c.likeCount + 1 WHERE c.id = :id")
    void incrementLikeCount(@Param("id") String id);

    @Modifying
    @Query("UPDATE CommunityRoute c SET c.likeCount = c.likeCount - 1 WHERE c.id = :id AND c.likeCount > 0")
    void decrementLikeCount(@Param("id") String id);
}
