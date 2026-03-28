package com.artrun.server.repository;

import com.artrun.server.domain.RunRecord;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RunRecordRepository extends JpaRepository<RunRecord, String> {}
