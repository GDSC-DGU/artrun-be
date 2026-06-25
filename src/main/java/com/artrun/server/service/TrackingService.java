package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import com.artrun.server.dto.request.TrackRequest;
import com.artrun.server.dto.response.TrackResponse;
import com.artrun.server.repository.RunSessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class TrackingService {

    private static final double OFF_ROUTE_THRESHOLD_METERS = 30.0;
    private static final double TURN_THRESHOLD_DEGREES = 30.0;
    private static final int VOICE_CUE_DISTANCE_METERS = 400;
    private static final int APPROACHING_TURN_METERS = 100;

    private final RunSessionRepository runSessionRepository;
    private final JdbcTemplate jdbcTemplate;

    @Transactional
    public TrackResponse checkPosition(String sessionId, TrackRequest request) {
        double lat = request.getLat();
        double lng = request.getLng();

        RunSession session = runSessionRepository.findById(sessionId)
                .orElseThrow(() -> new BusinessException(ErrorCode.SESSION_NOT_FOUND));

        if (session.getStatus() != SessionStatus.ACTIVE) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }

        Route route = session.getRoute();
        if (route == null || route.getPolyline() == null) {
            return TrackResponse.builder()
                    .sessionId(sessionId)
                    .status("RUNNING")
                    .onRoute(true)
                    .build();
        }

        Coordinate[] coords = route.getPolyline().getCoordinates();
        double[] cumDist = computeCumulativeDistances(coords);
        double totalDist = cumDist[coords.length - 1];

        int nearestIdx = findNearestPointIndex(coords, lat, lng);
        double distanceTraveled = cumDist[nearestIdx];
        double distanceRemaining = totalDist - distanceTraveled;
        int completionRate = totalDist > 0
                ? (int) Math.min(100, Math.round((distanceTraveled / totalDist) * 100.0))
                : 0;

        double distanceFromRoute = computeDistanceFromRoute(route, lat, lng);
        boolean isOnRoute = distanceFromRoute <= OFF_ROUTE_THRESHOLD_METERS;

        List<TurnPoint> turns = computeTurnPoints(coords, cumDist);
        List<TurnPoint> upcoming = turns.stream()
                .filter(t -> t.index() > nearestIdx)
                .toList();

        TrackResponse.InstructionDto currentInstruction = buildCurrentInstruction(upcoming, distanceTraveled, coords);
        TrackResponse.InstructionDto nextInstruction = buildNextInstruction(upcoming, distanceTraveled);
        TrackResponse.VoiceCueDto voiceCue = buildVoiceCue(nextInstruction);
        TrackResponse.PaceFeedbackDto paceFeedback = buildPaceFeedback(request.getCurrentSpeed(), session);
        TrackResponse.EdmControlDto edmControl = buildEdmControl(paceFeedback, session);

        session.setLastCompletionRate(completionRate);
        session.setLastDistanceTraveledMeters((int) distanceTraveled);
        session.setLastDistanceRemainingMeters((int) distanceRemaining);
        session.setLastTrackedAt(LocalDateTime.now());
        runSessionRepository.save(session);

        return TrackResponse.builder()
                .sessionId(sessionId)
                .routeId(route.getId())
                .status("RUNNING")
                .onRoute(isOnRoute)
                .completionRate(completionRate)
                .distanceTraveledMeters((int) distanceTraveled)
                .distanceRemainingMeters((int) distanceRemaining)
                .offRouteDistanceMeters((int) distanceFromRoute)
                .nearestRoutePointIndex(nearestIdx)
                .currentInstruction(currentInstruction)
                .nextInstruction(nextInstruction)
                .passedCheckpoint(null)
                .voiceCue(voiceCue)
                .paceFeedback(paceFeedback)
                .edmControl(edmControl)
                .warningMessage(isOnRoute ? null : "경로에서 이탈했습니다. 다시 경로로 돌아와주세요.")
                .build();
    }

    private double computeDistanceFromRoute(Route route, double lat, double lng) {
        String sql = """
                SELECT ST_Distance(
                    ST_GeomFromText(?, 4326)::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography
                )
                """;
        try {
            Double dist = jdbcTemplate.queryForObject(sql, Double.class, route.getPolyline().toText(), lng, lat);
            return dist != null ? dist : Double.MAX_VALUE;
        } catch (Exception e) {
            log.debug("Distance from route calculation failed: {}", e.getMessage());
            return Double.MAX_VALUE;
        }
    }

    private int findNearestPointIndex(Coordinate[] coords, double lat, double lng) {
        int nearestIdx = 0;
        double minDist = Double.MAX_VALUE;
        for (int i = 0; i < coords.length; i++) {
            double dx = coords[i].x - lng;
            double dy = coords[i].y - lat;
            double d = dx * dx + dy * dy;
            if (d < minDist) {
                minDist = d;
                nearestIdx = i;
            }
        }
        return nearestIdx;
    }

    private double[] computeCumulativeDistances(Coordinate[] coords) {
        double[] cumDist = new double[coords.length];
        for (int i = 1; i < coords.length; i++) {
            cumDist[i] = cumDist[i - 1] + haversineMeters(coords[i - 1].y, coords[i - 1].x, coords[i].y, coords[i].x);
        }
        return cumDist;
    }

    private List<TurnPoint> computeTurnPoints(Coordinate[] coords, double[] cumDist) {
        List<TurnPoint> turns = new ArrayList<>();
        int seq = 1;
        for (int i = 1; i < coords.length - 1; i++) {
            double b1 = bearing(coords[i - 1].y, coords[i - 1].x, coords[i].y, coords[i].x);
            double b2 = bearing(coords[i].y, coords[i].x, coords[i + 1].y, coords[i + 1].x);
            double turn = angleDiff(b1, b2);
            if (Math.abs(turn) >= TURN_THRESHOLD_DEGREES) {
                String type = turn > 0 ? "RIGHT" : "LEFT";
                int nextDist = (int) haversineMeters(coords[i].y, coords[i].x, coords[i + 1].y, coords[i + 1].x);
                String msg = String.format("%dm 앞에서 %s하세요.", nextDist, turn > 0 ? "우회전" : "좌회전");
                turns.add(new TurnPoint(i, "turn_" + seq, type, msg, coords[i].y, coords[i].x, cumDist[i]));
                seq++;
            }
        }
        return turns;
    }

    private TrackResponse.InstructionDto buildCurrentInstruction(
            List<TurnPoint> upcoming, double distanceTraveled, Coordinate[] coords) {
        if (upcoming.isEmpty()) {
            Coordinate last = coords[coords.length - 1];
            return TrackResponse.InstructionDto.builder()
                    .instructionId("finish")
                    .type("STRAIGHT")
                    .message("계속 직진하여 결승점으로 향하세요.")
                    .distanceToInstructionMeters(0)
                    .point(new TrackResponse.LatLng(last.y, last.x))
                    .build();
        }
        TurnPoint first = upcoming.get(0);
        int distToFirst = (int) (first.cumDist() - distanceTraveled);

        if (distToFirst <= APPROACHING_TURN_METERS) {
            return toInstructionDto(first, distToFirst);
        }
        return TrackResponse.InstructionDto.builder()
                .instructionId("straight_" + first.instructionId())
                .type("STRAIGHT")
                .message("계속 직진하세요.")
                .distanceToInstructionMeters(distToFirst)
                .point(new TrackResponse.LatLng(first.lat(), first.lng()))
                .build();
    }

    private TrackResponse.InstructionDto buildNextInstruction(List<TurnPoint> upcoming, double distanceTraveled) {
        if (upcoming.isEmpty()) return null;
        TurnPoint first = upcoming.get(0);
        int distToFirst = (int) (first.cumDist() - distanceTraveled);

        if (distToFirst <= APPROACHING_TURN_METERS && upcoming.size() > 1) {
            TurnPoint second = upcoming.get(1);
            return toInstructionDto(second, (int) (second.cumDist() - distanceTraveled));
        }
        return toInstructionDto(first, distToFirst);
    }

    private TrackResponse.InstructionDto toInstructionDto(TurnPoint turn, int distance) {
        return TrackResponse.InstructionDto.builder()
                .instructionId(turn.instructionId())
                .type(turn.type())
                .message(turn.message())
                .distanceToInstructionMeters(distance)
                .point(new TrackResponse.LatLng(turn.lat(), turn.lng()))
                .build();
    }

    private TrackResponse.VoiceCueDto buildVoiceCue(TrackResponse.InstructionDto nextInstruction) {
        if (nextInstruction == null || nextInstruction.getDistanceToInstructionMeters() > VOICE_CUE_DISTANCE_METERS) {
            return TrackResponse.VoiceCueDto.builder().shouldSpeak(false).build();
        }
        String direction = "LEFT".equals(nextInstruction.getType()) ? "좌회전" : "우회전";
        String voiceMessage = nextInstruction.getDistanceToInstructionMeters() + "미터 앞에서 " + direction + "하세요.";
        return TrackResponse.VoiceCueDto.builder()
                .shouldSpeak(true)
                .priority("NORMAL")
                .message(voiceMessage)
                .cueType("TURN")
                .speakKey(nextInstruction.getInstructionId() + "_" + nextInstruction.getDistanceToInstructionMeters() + "m")
                .build();
    }

    private TrackResponse.PaceFeedbackDto buildPaceFeedback(Double currentSpeed, RunSession session) {
        Integer targetPace = session.getTargetPaceSecPerKm();
        if (targetPace == null || currentSpeed == null || currentSpeed <= 0) return null;

        int currentPace = (int) (1000.0 / currentSpeed);
        double ratio = (double) currentPace / targetPace;

        String paceStatus;
        String message;
        if (ratio > 1.1) {
            paceStatus = "TOO_SLOW";
            message = "목표보다 느립니다. BPM을 높여 리듬을 끌어올립니다.";
        } else if (ratio < 0.9) {
            paceStatus = "TOO_FAST";
            message = "목표보다 빠릅니다. BPM을 낮춰 페이스를 유지합니다.";
        } else {
            paceStatus = "ON_PACE";
            message = "적절한 페이스입니다.";
        }

        return TrackResponse.PaceFeedbackDto.builder()
                .targetPaceSecPerKm(targetPace)
                .currentPaceSecPerKm(currentPace)
                .paceStatus(paceStatus)
                .message(message)
                .build();
    }

    private TrackResponse.EdmControlDto buildEdmControl(TrackResponse.PaceFeedbackDto paceFeedback, RunSession session) {
        if (!Boolean.TRUE.equals(session.getEdmControlEnabled())) {
            return TrackResponse.EdmControlDto.builder().enabled(false).build();
        }

        int baseBpm = 156;
        Route route = session.getRoute();
        if (route != null && route.getTask() != null) {
            String activityType = route.getTask().getActivityType();
            if ("WALKING".equalsIgnoreCase(activityType)) baseBpm = 100;
            else if ("CYCLING".equalsIgnoreCase(activityType)) baseBpm = 130;
        }

        String action = "MAINTAIN";
        int targetBpm = baseBpm;
        String reason = "적절한 페이스";

        if (paceFeedback != null) {
            if ("TOO_SLOW".equals(paceFeedback.getPaceStatus())) {
                action = "INCREASE";
                targetBpm = baseBpm + 8;
                reason = "목표 페이스보다 느림";
            } else if ("TOO_FAST".equals(paceFeedback.getPaceStatus())) {
                action = "DECREASE";
                targetBpm = baseBpm - 8;
                reason = "목표 페이스보다 빠름";
            }
        }

        return TrackResponse.EdmControlDto.builder()
                .enabled(true)
                .currentBpm(baseBpm)
                .targetBpm(targetBpm)
                .action(action)
                .reason(reason)
                .build();
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

    private double bearing(double lat1, double lng1, double lat2, double lng2) {
        double dLng = Math.toRadians(lng2 - lng1);
        double lat1R = Math.toRadians(lat1);
        double lat2R = Math.toRadians(lat2);
        double y = Math.sin(dLng) * Math.cos(lat2R);
        double x = Math.cos(lat1R) * Math.sin(lat2R) - Math.sin(lat1R) * Math.cos(lat2R) * Math.cos(dLng);
        return Math.toDegrees(Math.atan2(y, x));
    }

    private double angleDiff(double b1, double b2) {
        double diff = ((b2 - b1) % 360 + 360) % 360;
        if (diff > 180) diff -= 360;
        return diff;
    }

    private record TurnPoint(int index, String instructionId, String type, String message,
                             double lat, double lng, double cumDist) {}
}
