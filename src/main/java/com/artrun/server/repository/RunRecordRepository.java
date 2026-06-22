package com.artrun.server.repository;

import com.artrun.server.domain.RunRecord;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface RunRecordRepository extends JpaRepository<RunRecord, String> {
    Page<RunRecord> findByUser_IdOrderByCreatedAtDesc(String userId, Pageable pageable);
    Optional<RunRecord> findByIdAndUser_Id(String id, String userId);

    @Query("SELECT COALESCE(SUM(r.totalDistanceMeters), 0) FROM RunRecord r WHERE r.user.id = :userId")
    double sumDistanceByUserId(@Param("userId") String userId);

    @Query("SELECT COALESCE(SUM(r.totalTimeSeconds), 0) FROM RunRecord r WHERE r.user.id = :userId")
    long sumTimeByUserId(@Param("userId") String userId);

    long countByUser_Id(String userId);
}
