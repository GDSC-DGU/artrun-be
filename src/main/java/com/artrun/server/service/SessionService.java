package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import com.artrun.server.domain.User;
import com.artrun.server.dto.request.CancelSessionRequest;
import com.artrun.server.dto.request.FinishSessionRequest;
import com.artrun.server.dto.request.ResumeSessionRequest;
import com.artrun.server.dto.request.StartSessionRequest;
import com.artrun.server.dto.response.CancelSessionResponse;
import com.artrun.server.dto.response.FinishSessionResponse;
import com.artrun.server.dto.response.PauseSessionResponse;
import com.artrun.server.dto.response.ResumeSessionResponse;
import com.artrun.server.dto.response.SessionDetailResponse;
import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.dto.response.StartSessionResponse;
import org.locationtech.jts.geom.Coordinate;
import com.artrun.server.repository.RouteRepository;
import com.artrun.server.repository.RunSessionRepository;
import com.artrun.server.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class SessionService {

    private final RunSessionRepository runSessionRepository;
    private final RouteRepository routeRepository;
    private final UserRepository userRepository;
    private final JdbcTemplate jdbcTemplate;

    private static final double START_THRESHOLD_METERS = 200.0;

    @Transactional
    public StartSessionResponse startSession(String userId, StartSessionRequest request) {
        Route route = routeRepository.findById(request.getRouteId())
                .orElseThrow(() -> new BusinessException(ErrorCode.ROUTE_NOT_FOUND));

        if (runSessionRepository.existsByUser_IdAndRoute_IdAndStatus(userId, request.getRouteId(), SessionStatus.ACTIVE)) {
            throw new BusinessException(ErrorCode.SESSION_ALREADY_ACTIVE);
        }

        double distanceToStart = computeDistanceToStart(request.getCurrentPoint(), route);
        if (distanceToStart > START_THRESHOLD_METERS) {
            return StartSessionResponse.builder()
                    .sessionId(null)
                    .routeId(request.getRouteId())
                    .status("REJECTED")
                    .startAllowed(false)
                    .startDistanceMeters(distanceToStart)
                    .message("시작점 200m 이내에서 러닝을 시작해주세요.")
                    .startedAt(null)
                    .build();
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        RunSession session = RunSession.builder()
                .user(user)
                .route(route)
                .status(SessionStatus.ACTIVE)
                .startedAt(LocalDateTime.now())
                .targetPaceSecPerKm(request.getTargetPaceSecPerKm())
                .voiceGuideEnabled(request.isVoiceGuideEnabled())
                .edmControlEnabled(request.isEdmControlEnabled())
                .build();

        RunSession saved = runSessionRepository.save(session);
        log.info("Session started: sessionId={}, routeId={}, userId={}", saved.getId(), request.getRouteId(), userId);

        return StartSessionResponse.builder()
                .sessionId(saved.getId())
                .routeId(request.getRouteId())
                .status("RUNNING")
                .startAllowed(true)
                .startDistanceMeters(distanceToStart)
                .message("러닝을 시작할 수 있습니다.")
                .startedAt(saved.getStartedAt())
                .build();
    }

    private double computeDistanceToStart(StartSessionRequest.CurrentPointDto currentPoint, Route route) {
        if (currentPoint == null) return Double.MAX_VALUE;
        double userLat = currentPoint.getLat();
        double userLng = currentPoint.getLng();
        double startLat, startLng;
        if (route.getTask() != null && route.getTask().getStartPoint() != null) {
            startLat = route.getTask().getStartPoint().getY();
            startLng = route.getTask().getStartPoint().getX();
        } else if (route.getPolyline() != null && route.getPolyline().getNumPoints() > 0) {
            Coordinate first = route.getPolyline().getCoordinateN(0);
            startLat = first.y;
            startLng = first.x;
        } else {
            return 0;
        }
        return haversineMeters(userLat, userLng, startLat, startLng);
    }

    private double haversineMeters(double lat1, double lng1, double lat2, double lng2) {
        final double R = 6371000;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    @Transactional
    public PauseSessionResponse pauseSession(String userId, String sessionId) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() != SessionStatus.ACTIVE) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.PAUSED);
        session.setPausedAt(LocalDateTime.now());
        RunSession saved = runSessionRepository.save(session);
        return PauseSessionResponse.builder()
                .sessionId(saved.getId())
                .status(SessionStatus.PAUSED.name())
                .pausedAt(saved.getPausedAt())
                .build();
    }

    @Transactional
    public ResumeSessionResponse resumeSession(String userId, String sessionId, ResumeSessionRequest request) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() != SessionStatus.PAUSED) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.ACTIVE);
        session.setResumedAt(LocalDateTime.now());
        RunSession saved = runSessionRepository.save(session);

        StartSessionRequest.CurrentPointDto cp = request.getCurrentPoint();
        double distanceFromRoute = computeDistanceFromRoute(session.getRoute(), cp.getLat(), cp.getLng());
        boolean onRoute = distanceFromRoute <= 30.0;

        return ResumeSessionResponse.builder()
                .sessionId(saved.getId())
                .status("RUNNING")
                .resumedAt(saved.getResumedAt())
                .onRoute(onRoute)
                .offRouteDistanceMeters((int) distanceFromRoute)
                .build();
    }

    private double computeDistanceFromRoute(Route route, double lat, double lng) {
        if (route == null || route.getPolyline() == null) return 0.0;
        String sql = """
                SELECT ST_Distance(
                    ST_GeomFromText(?, 4326)::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography
                )
                """;
        try {
            Double dist = jdbcTemplate.queryForObject(sql, Double.class, route.getPolyline().toText(), lng, lat);
            return dist != null ? dist : 0.0;
        } catch (Exception e) {
            log.debug("Distance from route calculation failed: {}", e.getMessage());
            return 0.0;
        }
    }

    @Transactional
    public FinishSessionResponse finishSession(String userId, String sessionId, FinishSessionRequest request) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() != SessionStatus.ACTIVE && session.getStatus() != SessionStatus.PAUSED) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.FINISHED);
        session.setFinishedAt(LocalDateTime.now());
        if (request.getTotalTimeSeconds() != null) {
            session.setTotalTimeSeconds(request.getTotalTimeSeconds());
        }
        RunSession saved = runSessionRepository.save(session);

        int completionRate = computeCompletionRate(session.getRoute(), request.getCurrentPoint());

        return FinishSessionResponse.builder()
                .sessionId(saved.getId())
                .routeId(saved.getRoute().getId())
                .status("COMPLETED")
                .completionRate(completionRate)
                .recordSaveRequired(true)
                .message(completionRate >= 100 ? "러닝 루트를 완주했습니다." : "러닝이 종료되었습니다.")
                .build();
    }

    private int computeCompletionRate(Route route, StartSessionRequest.CurrentPointDto currentPoint) {
        if (route == null || route.getPolyline() == null || currentPoint == null) return 100;
        String sql = """
                SELECT ROUND(ST_LineLocatePoint(
                    ST_GeomFromText(?, 4326),
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)
                ) * 100)::int
                """;
        try {
            Integer rate = jdbcTemplate.queryForObject(sql, Integer.class,
                    route.getPolyline().toText(), currentPoint.getLng(), currentPoint.getLat());
            return rate != null ? Math.min(100, Math.max(0, rate)) : 100;
        } catch (Exception e) {
            log.debug("Completion rate calculation failed: {}", e.getMessage());
            return 100;
        }
    }

    @Transactional
    public CancelSessionResponse cancelSession(String userId, String sessionId, CancelSessionRequest request) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() == SessionStatus.COMPLETED || session.getStatus() == SessionStatus.CANCELLED) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.CANCELLED);
        session.setCanceledAt(LocalDateTime.now());
        session.setCancelReason(request != null ? request.getReason() : null);
        RunSession saved = runSessionRepository.save(session);
        return CancelSessionResponse.builder()
                .sessionId(saved.getId())
                .status("CANCELED")
                .canceledAt(saved.getCanceledAt())
                .build();
    }

    @Transactional(readOnly = true)
    public SessionDetailResponse getSession(String userId, String sessionId) {
        RunSession session = getOwnedSession(userId, sessionId);
        return SessionDetailResponse.builder()
                .sessionId(session.getId())
                .routeId(session.getRoute().getId())
                .status(mapStatus(session.getStatus()))
                .completionRate(session.getLastCompletionRate())
                .distanceTraveledMeters(session.getLastDistanceTraveledMeters())
                .distanceRemainingMeters(session.getLastDistanceRemainingMeters())
                .startedAt(session.getStartedAt())
                .pausedAt(session.getPausedAt())
                .lastTrackedAt(session.getLastTrackedAt())
                .build();
    }

    private String mapStatus(SessionStatus status) {
        return switch (status) {
            case ACTIVE -> "RUNNING";
            case CANCELLED -> "CANCELED";
            default -> status.name();
        };
    }

    private RunSession getOwnedSession(String userId, String sessionId) {
        return runSessionRepository.findByIdAndUser_Id(sessionId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.SESSION_NOT_FOUND));
    }
}
