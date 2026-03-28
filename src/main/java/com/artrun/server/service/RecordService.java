package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.RunRecord;
import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import com.artrun.server.dto.request.SaveRecordRequest;
import com.artrun.server.dto.response.RecordResponse;
import com.artrun.server.repository.RunRecordRepository;
import com.artrun.server.repository.RunSessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class RecordService {

    private static final GeometryFactory GEOMETRY_FACTORY = new GeometryFactory(new PrecisionModel(), 4326);

    private final RunSessionRepository runSessionRepository;
    private final RunRecordRepository runRecordRepository;
    private final JdbcTemplate jdbcTemplate;

    @Transactional
    public RecordResponse saveRecord(SaveRecordRequest request) {
        RunSession session = runSessionRepository.findById(request.getSessionId())
                .orElseThrow(() -> new BusinessException(ErrorCode.SESSION_NOT_FOUND));

        // 세션 완료 처리
        session.setStatus(SessionStatus.COMPLETED);
        session.setFinishedAt(LocalDateTime.now());
        runSessionRepository.save(session);

        // raw GPS → LineString
        LineString rawPolyline = createLineString(request.getGpsPoints());

        // GPS 보정 (PostGIS ST_SnapToGrid)
        LineString correctedPolyline = correctGps(rawPolyline);

        // 총 거리 계산
        Double totalDistance = calculateDistance(correctedPolyline);

        // 평균 속도 계산 (m/s)
        Double avgSpeed = request.getTotalTimeSeconds() > 0
                ? totalDistance / request.getTotalTimeSeconds()
                : 0.0;

        RunRecord record = RunRecord.builder()
                .session(session)
                .rawPolyline(rawPolyline)
                .correctedPolyline(correctedPolyline)
                .totalDistanceMeters(totalDistance)
                .totalTimeSeconds(request.getTotalTimeSeconds())
                .averageSpeed(avgSpeed)
                .build();

        RunRecord saved = runRecordRepository.save(record);

        return RecordResponse.builder()
                .recordId(saved.getId())
                .totalDistanceMeters(totalDistance)
                .totalTimeSeconds(request.getTotalTimeSeconds())
                .averageSpeed(avgSpeed)
                .imageUrl(saved.getImageUrl())
                .build();
    }

    private LineString createLineString(List<SaveRecordRequest.GpsPoint> points) {
        Coordinate[] coords = points.stream()
                .map(p -> new Coordinate(p.getLng(), p.getLat()))
                .toArray(Coordinate[]::new);
        return GEOMETRY_FACTORY.createLineString(coords);
    }

    private LineString correctGps(LineString raw) {
        // ST_SnapToGrid로 GPS 노이즈 제거 (약 1m 그리드)
        String sql = """
                SELECT ST_AsText(
                    ST_SnapToGrid(ST_GeomFromText(?, 4326), 0.00001)
                )
                """;
        try {
            String wkt = jdbcTemplate.queryForObject(sql, String.class, raw.toText());
            if (wkt != null) {
                org.locationtech.jts.io.WKTReader reader = new org.locationtech.jts.io.WKTReader(GEOMETRY_FACTORY);
                Geometry geom = reader.read(wkt);
                if (geom instanceof LineString ls) return ls;
            }
        } catch (Exception e) {
            log.warn("GPS correction failed, using raw data: {}", e.getMessage());
        }
        return raw;
    }

    private Double calculateDistance(LineString polyline) {
        String sql = "SELECT ST_Length(ST_GeomFromText(?, 4326)::geography)";
        return jdbcTemplate.queryForObject(sql, Double.class, polyline.toText());
    }
}
