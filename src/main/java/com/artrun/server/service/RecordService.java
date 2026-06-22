package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.*;
import com.artrun.server.dto.request.SaveRecordRequest;
import com.artrun.server.dto.response.RecordDetailResponse;
import com.artrun.server.dto.response.RecordResponse;
import com.artrun.server.repository.CommunityRouteRepository;
import com.artrun.server.repository.RunRecordRepository;
import com.artrun.server.repository.RunSessionRepository;
import com.artrun.server.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class RecordService {

    private static final GeometryFactory GEOMETRY_FACTORY = new GeometryFactory(new PrecisionModel(), 4326);

    private final RunSessionRepository runSessionRepository;
    private final RunRecordRepository runRecordRepository;
    private final CommunityRouteRepository communityRouteRepository;
    private final UserRepository userRepository;
    private final JdbcTemplate jdbcTemplate;
    private final ShareCardService shareCardService;

    @Transactional
    public RecordResponse saveRecord(String userId, SaveRecordRequest request) {
        RunSession session = runSessionRepository.findByIdAndUser_Id(request.getSessionId(), userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.SESSION_NOT_FOUND));

        if (session.getStatus() != SessionStatus.FINISHED) {
            throw new BusinessException(ErrorCode.SESSION_NOT_FINISHED);
        }

        LineString rawPolyline = createLineString(request.getGpsPoints());
        LineString correctedPolyline = correctGps(rawPolyline);
        Double totalDistance = calculateDistance(correctedPolyline);
        if (totalDistance == null) totalDistance = 0.0;

        double avgSpeed = request.getTotalTimeSeconds() > 0
                ? totalDistance / request.getTotalTimeSeconds()
                : 0.0;

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        RunRecord record = RunRecord.builder()
                .user(user)
                .session(session)
                .rawPolyline(rawPolyline)
                .correctedPolyline(correctedPolyline)
                .totalDistanceMeters(totalDistance)
                .totalTimeSeconds(request.getTotalTimeSeconds())
                .averageSpeed(avgSpeed)
                .build();

        RunRecord saved = runRecordRepository.save(record);

        // 공유 카드 생성
        String imageUrl = shareCardService.generateAndUpload(saved);
        if (imageUrl != null) {
            saved.setImageUrl(imageUrl);
            saved = runRecordRepository.save(saved);
        }

        session.setStatus(SessionStatus.COMPLETED);
        runSessionRepository.save(session);

        return RecordResponse.builder()
                .recordId(saved.getId())
                .totalDistanceMeters(totalDistance)
                .totalTimeSeconds(request.getTotalTimeSeconds())
                .averageSpeed(avgSpeed)
                .imageUrl(saved.getImageUrl())
                .build();
    }

    @Transactional(readOnly = true)
    public RecordDetailResponse getRecord(String userId, String recordId) {
        RunRecord record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        List<RecordDetailResponse.LatLng> planned = toLatLngs(
                record.getSession().getRoute().getPolyline());
        List<RecordDetailResponse.LatLng> actual = toLatLngs(record.getCorrectedPolyline());

        return RecordDetailResponse.builder()
                .recordId(record.getId())
                .routeId(record.getSession().getRoute().getId())
                .plannedPolyline(planned)
                .actualPolyline(actual)
                .totalDistanceMeters(record.getTotalDistanceMeters())
                .totalTimeSeconds(record.getTotalTimeSeconds())
                .averageSpeed(record.getAverageSpeed())
                .imageUrl(record.getImageUrl())
                .createdAt(record.getCreatedAt())
                .build();
    }

    @Transactional
    public String regenerateShareCard(String userId, String recordId) {
        RunRecord record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        String imageUrl = shareCardService.generateAndUpload(record);
        if (imageUrl != null) {
            record.setImageUrl(imageUrl);
            runRecordRepository.save(record);
        }
        return imageUrl;
    }

    @Transactional
    public void deleteRecord(String userId, String recordId) {
        RunRecord record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        if (communityRouteRepository.existsByRecord_Id(recordId)) {
            throw new BusinessException(ErrorCode.RECORD_IN_COMMUNITY);
        }

        runRecordRepository.delete(record);
    }

    private LineString createLineString(List<SaveRecordRequest.GpsPoint> points) {
        Coordinate[] coords = points.stream()
                .map(p -> new Coordinate(p.getLng(), p.getLat()))
                .toArray(Coordinate[]::new);
        return GEOMETRY_FACTORY.createLineString(coords);
    }

    private LineString correctGps(LineString raw) {
        String sql = "SELECT ST_AsText(ST_SnapToGrid(ST_GeomFromText(?, 4326), 0.00001))";
        try {
            String wkt = jdbcTemplate.queryForObject(sql, String.class, raw.toText());
            if (wkt != null) {
                Geometry geom = new org.locationtech.jts.io.WKTReader(GEOMETRY_FACTORY).read(wkt);
                if (geom instanceof LineString ls) return ls;
            }
        } catch (Exception e) {
            log.warn("GPS correction failed, using raw data: {}", e.getMessage());
        }
        return raw;
    }

    private Double calculateDistance(LineString polyline) {
        return jdbcTemplate.queryForObject(
                "SELECT ST_Length(ST_GeomFromText(?, 4326)::geography)",
                Double.class, polyline.toText());
    }

    private List<RecordDetailResponse.LatLng> toLatLngs(LineString line) {
        if (line == null) return List.of();
        return Arrays.stream(line.getCoordinates())
                .map(c -> RecordDetailResponse.LatLng.builder().lat(c.y).lng(c.x).build())
                .toList();
    }
}
