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

import com.artrun.server.dto.request.ShareCardRequest;
import com.artrun.server.dto.response.ShareCardResponse;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class RecordService {

    private static final GeometryFactory GEOMETRY_FACTORY = new GeometryFactory(new PrecisionModel(), 4326);
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

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

        Route route = session.getRoute();
        int pace = request.getAveragePaceSecPerKm() != null ? request.getAveragePaceSecPerKm()
                : (avgSpeed > 0 ? (int) (1000.0 / avgSpeed) : 0);
        int bpm = request.getAverageBpm() != null ? request.getAverageBpm() : 0;
        int calories = request.getCalories() != null ? request.getCalories() : 0;
        int matchRate = computeMatchRate(correctedPolyline, route != null ? route.getPolyline() : null);
        int completionRate = session.getLastCompletionRate() != null ? session.getLastCompletionRate() : 100;

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        String rawGpsJson = serializeGpsPoints(request.getGpsPoints());

        RunRecord record = RunRecord.builder()
                .user(user)
                .session(session)
                .rawPolyline(rawPolyline)
                .correctedPolyline(correctedPolyline)
                .totalDistanceMeters(totalDistance)
                .totalTimeSeconds(request.getTotalTimeSeconds())
                .averageSpeed(avgSpeed)
                .averagePaceSecPerKm(pace)
                .averageBpm(bpm)
                .calories(calories)
                .matchRate(matchRate)
                .completionRate(completionRate)
                .rawGpsJson(rawGpsJson)
                .build();

        RunRecord saved = runRecordRepository.save(record);

        String imageUrl = shareCardService.generateAndUpload(saved);
        if (imageUrl != null) {
            saved.setImageUrl(imageUrl);
            saved = runRecordRepository.save(saved);
        }

        session.setStatus(SessionStatus.COMPLETED);
        runSessionRepository.save(session);

        String routeName = route != null ? route.getRouteName() : null;
        String shapeType = (route != null && route.getTask() != null) ? route.getTask().getShapeType() : null;
        double totalDistanceKm = Math.round(totalDistance / 10.0) / 100.0;

        List<RecordResponse.PolylinePoint> correctedPoints = buildCorrectedPolyline(
                correctedPolyline, request.getGpsPoints());

        return RecordResponse.builder()
                .recordId(saved.getId())
                .sessionId(session.getId())
                .routeId(route != null ? route.getId() : null)
                .routeName(routeName)
                .shapeType(shapeType)
                .totalDistanceMeters(totalDistance)
                .totalDistanceKm(totalDistanceKm)
                .totalTimeSeconds(request.getTotalTimeSeconds())
                .averagePaceSecPerKm(pace)
                .averagePaceText(formatPace(pace))
                .averageSpeed(Math.round(avgSpeed * 100.0) / 100.0)
                .averageBpm(bpm)
                .calories(calories)
                .matchRate(matchRate)
                .completionRate(completionRate)
                .correctedPolyline(correctedPoints)
                .imageUrl(saved.getImageUrl())
                .createdAt(saved.getCreatedAt())
                .build();
    }

    private String formatPace(int paceSecPerKm) {
        if (paceSecPerKm <= 0) return "0'00\"";
        int minutes = paceSecPerKm / 60;
        int seconds = paceSecPerKm % 60;
        return String.format("%d'%02d\"", minutes, seconds);
    }

    private int computeMatchRate(LineString actual, LineString planned) {
        if (actual == null || planned == null) return 0;
        Coordinate[] actualCoords = actual.getCoordinates();
        Coordinate[] plannedCoords = planned.getCoordinates();
        if (actualCoords.length == 0) return 0;
        int onRoute = 0;
        for (Coordinate c : actualCoords) {
            double minDist = Double.MAX_VALUE;
            for (Coordinate p : plannedCoords) {
                double d = haversineMeters(c.y, c.x, p.y, p.x);
                if (d < minDist) minDist = d;
            }
            if (minDist <= 30.0) onRoute++;
        }
        return onRoute * 100 / actualCoords.length;
    }

    private List<RecordResponse.PolylinePoint> buildCorrectedPolyline(
            LineString corrected, List<SaveRecordRequest.GpsPoint> originals) {
        Coordinate[] coords = corrected.getCoordinates();
        List<RecordResponse.PolylinePoint> result = new ArrayList<>();
        for (int i = 0; i < coords.length; i++) {
            Long ts = (originals != null && i < originals.size()) ? originals.get(i).getTimestamp() : null;
            result.add(RecordResponse.PolylinePoint.builder()
                    .lat(coords[i].y)
                    .lng(coords[i].x)
                    .order(i + 1)
                    .timestamp(ts)
                    .build());
        }
        return result;
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

    @Transactional(readOnly = true)
    public RecordDetailResponse getRecord(String userId, String recordId) {
        RunRecord record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        Route route = record.getSession().getRoute();
        double totalDistanceKm = Math.round((record.getTotalDistanceMeters() != null ? record.getTotalDistanceMeters() : 0) / 10.0) / 100.0;
        int pace = record.getAveragePaceSecPerKm() != null ? record.getAveragePaceSecPerKm() : 0;

        List<RecordDetailResponse.TargetRoutePoint> targetRoute = buildTargetRoutePolyline(
                route != null ? route.getPolyline() : null);
        List<RecordDetailResponse.ActualGpsPoint> actualGps = buildActualGpsPoints(record.getRawGpsJson());
        List<RecordDetailResponse.CorrectedPolylinePoint> corrected = buildCorrectedPolylineDetail(
                record.getCorrectedPolyline(), actualGps);

        boolean communityShared = communityRouteRepository.existsByRecord_Id(recordId);

        return RecordDetailResponse.builder()
                .recordId(record.getId())
                .sessionId(record.getSession().getId())
                .routeId(route != null ? route.getId() : null)
                .routeName(route != null ? route.getRouteName() : null)
                .shapeType(route != null && route.getTask() != null ? route.getTask().getShapeType() : null)
                .totalDistanceKm(totalDistanceKm)
                .totalTimeSeconds(record.getTotalTimeSeconds() != null ? record.getTotalTimeSeconds() : 0)
                .averagePaceSecPerKm(pace)
                .averagePaceText(formatPace(pace))
                .averageSpeed(record.getAverageSpeed() != null ? Math.round(record.getAverageSpeed() * 100.0) / 100.0 : 0)
                .averageBpm(record.getAverageBpm() != null ? record.getAverageBpm() : 0)
                .calories(record.getCalories() != null ? record.getCalories() : 0)
                .matchRate(record.getMatchRate() != null ? record.getMatchRate() : 0)
                .completionRate(record.getCompletionRate() != null ? record.getCompletionRate() : 0)
                .targetRoutePolyline(targetRoute)
                .actualGpsPoints(actualGps)
                .correctedPolyline(corrected)
                .imageUrl(record.getImageUrl())
                .communityShared(communityShared)
                .createdAt(record.getCreatedAt())
                .build();
    }

    @Transactional
    public ShareCardResponse regenerateShareCard(String userId, String recordId, ShareCardRequest request) {
        RunRecord record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        String imageUrl = shareCardService.generateAndUpload(record);
        if (imageUrl != null) {
            record.setImageUrl(imageUrl);
            runRecordRepository.save(record);
        }
        return ShareCardResponse.builder()
                .recordId(recordId)
                .imageUrl(record.getImageUrl())
                .generatedAt(java.time.LocalDateTime.now())
                .build();
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

    private List<RecordDetailResponse.TargetRoutePoint> buildTargetRoutePolyline(LineString line) {
        if (line == null) return List.of();
        Coordinate[] coords = line.getCoordinates();
        List<RecordDetailResponse.TargetRoutePoint> result = new ArrayList<>();
        for (int i = 0; i < coords.length; i++) {
            result.add(RecordDetailResponse.TargetRoutePoint.builder()
                    .lat(coords[i].y).lng(coords[i].x).order(i + 1).build());
        }
        return result;
    }

    private List<RecordDetailResponse.ActualGpsPoint> buildActualGpsPoints(String rawGpsJson) {
        if (rawGpsJson == null) return List.of();
        try {
            List<SaveRecordRequest.GpsPoint> points = OBJECT_MAPPER.readValue(
                    rawGpsJson, new TypeReference<>() {});
            return points.stream()
                    .map(p -> RecordDetailResponse.ActualGpsPoint.builder()
                            .lat(p.getLat()).lng(p.getLng())
                            .timestamp(p.getTimestamp())
                            .accuracyMeters(p.getAccuracyMeters())
                            .speed(p.getSpeed())
                            .build())
                    .toList();
        } catch (Exception e) {
            log.warn("Failed to deserialize rawGpsJson: {}", e.getMessage());
            return List.of();
        }
    }

    private List<RecordDetailResponse.CorrectedPolylinePoint> buildCorrectedPolylineDetail(
            LineString corrected, List<RecordDetailResponse.ActualGpsPoint> actualGps) {
        if (corrected == null) return List.of();
        Coordinate[] coords = corrected.getCoordinates();
        List<RecordDetailResponse.CorrectedPolylinePoint> result = new ArrayList<>();
        for (int i = 0; i < coords.length; i++) {
            Long ts = (actualGps != null && i < actualGps.size()) ? actualGps.get(i).getTimestamp() : null;
            result.add(RecordDetailResponse.CorrectedPolylinePoint.builder()
                    .lat(coords[i].y).lng(coords[i].x).order(i + 1).timestamp(ts).build());
        }
        return result;
    }

    private String serializeGpsPoints(List<SaveRecordRequest.GpsPoint> points) {
        if (points == null) return null;
        try {
            return OBJECT_MAPPER.writeValueAsString(points);
        } catch (Exception e) {
            log.warn("Failed to serialize GPS points: {}", e.getMessage());
            return null;
        }
    }
}
