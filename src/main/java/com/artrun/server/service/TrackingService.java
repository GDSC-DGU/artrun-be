package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RunSession;
import com.artrun.server.dto.response.TrackResponse;
import com.artrun.server.repository.RunSessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class TrackingService {

    private static final double OFF_ROUTE_THRESHOLD_METERS = 30.0;

    private final RunSessionRepository runSessionRepository;
    private final JdbcTemplate jdbcTemplate;

    @Transactional(readOnly = true)
    public TrackResponse checkPosition(String sessionId, double lat, double lng) {
        RunSession session = runSessionRepository.findById(sessionId)
                .orElseThrow(() -> new BusinessException(ErrorCode.SESSION_NOT_FOUND));

        Route route = session.getRoute();
        if (route == null || route.getPolyline() == null) {
            return TrackResponse.builder()
                    .onRoute(true)
                    .build();
        }

        // 현재 위치와 경로 간 거리 계산
        String distanceSql = """
                SELECT ST_Distance(
                    ST_GeomFromText(?, 4326)::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography
                )
                """;
        Double distanceFromRoute = jdbcTemplate.queryForObject(
                distanceSql, Double.class, route.getPolyline().toText(), lng, lat);

        boolean isOnRoute = distanceFromRoute != null && distanceFromRoute <= OFF_ROUTE_THRESHOLD_METERS;

        // 남은 거리 계산
        String remainingSql = """
                SELECT ST_Length(ST_GeomFromText(?, 4326)::geography)
                - ST_Length(
                    ST_LineSubstring(
                        ST_GeomFromText(?, 4326),
                        0,
                        ST_LineLocatePoint(ST_GeomFromText(?, 4326), ST_SetSRID(ST_MakePoint(?, ?), 4326))
                    )::geography
                )
                """;
        Double remaining = null;
        try {
            remaining = jdbcTemplate.queryForObject(remainingSql, Double.class,
                    route.getPolyline().toText(),
                    route.getPolyline().toText(),
                    route.getPolyline().toText(),
                    lng, lat);
        } catch (Exception e) {
            log.debug("Remaining distance calculation failed: {}", e.getMessage());
        }

        // 완주율 계산
        Double completionRate = null;
        if (route.getDistanceMeters() != null && route.getDistanceMeters() > 0 && remaining != null) {
            completionRate = ((route.getDistanceMeters() - remaining) / route.getDistanceMeters()) * 100.0;
            completionRate = Math.max(0, Math.min(100, completionRate));
        }

        String warning = isOnRoute ? null : "경로에서 이탈했습니다. 다시 경로로 돌아와주세요.";

        return TrackResponse.builder()
                .onRoute(isOnRoute)
                .distanceRemaining(remaining)
                .completionRate(completionRate)
                .warningMessage(warning)
                .build();
    }
}
