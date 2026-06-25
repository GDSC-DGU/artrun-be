package com.artrun.server.repository;

import com.artrun.server.domain.CommunityRoute;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CommunityRouteRepository extends JpaRepository<CommunityRoute, String> {

    Page<CommunityRoute> findByUser_IdOrderByCreatedAtDesc(String userId, Pageable pageable);
    long countByUser_Id(String userId);
    boolean existsByRecord_Id(String recordId);

    @Query("SELECT cr.record.id FROM CommunityRoute cr WHERE cr.user.id = :userId")
    java.util.Set<String> findSharedRecordIdsByUserId(@Param("userId") String userId);

    @Query("""
            SELECT cr FROM CommunityRoute cr
            WHERE (:keyword IS NULL
                OR LOWER(cr.title) LIKE LOWER(CONCAT('%', :keyword, '%'))
                OR LOWER(cr.locationName) LIKE LOWER(CONCAT('%', :keyword, '%')))
            """)
    Page<CommunityRoute> searchByKeyword(@Param("keyword") String keyword, Pageable pageable);

    @Query("""
            SELECT cr FROM CommunityRoute cr JOIN cr.record r
            WHERE (:keyword IS NULL
                OR LOWER(cr.title) LIKE LOWER(CONCAT('%', :keyword, '%'))
                OR LOWER(cr.locationName) LIKE LOWER(CONCAT('%', :keyword, '%')))
            ORDER BY r.matchRate DESC NULLS LAST
            """)
    Page<CommunityRoute> searchOrderByMatchRateDesc(@Param("keyword") String keyword, Pageable pageable);

    @Modifying
    @Query("UPDATE CommunityRoute c SET c.likeCount = c.likeCount + 1 WHERE c.id = :id")
    void incrementLikeCount(@Param("id") String id);

    @Modifying
    @Query("UPDATE CommunityRoute c SET c.likeCount = c.likeCount - 1 WHERE c.id = :id AND c.likeCount > 0")
    void decrementLikeCount(@Param("id") String id);
}
