package com.artrun.server.service;

import com.artrun.server.domain.Route;
import com.artrun.server.domain.RouteTask;
import com.artrun.server.domain.TaskStatus;
import com.artrun.server.dto.AnchorPoint;
import com.artrun.server.repository.RouteRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.geom.LineString;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class RouteGenerationOrchestrator {

    private static final int MAX_CANDIDATES = 3;
    private static final double[] ROTATION_ANGLES = {0.0, 15.0, -15.0};

    private final TaskService taskService;
    private final ShapeEngineService shapeEngineService;
    private final GeospatialScaleService geospatialScaleService;
    private final MapMatchingService mapMatchingService;
    private final RoutingEngineService routingEngineService;
    private final ValidationScoringService validationScoringService;
    private final RouteRepository routeRepository;

    @Async("routeGenerationExecutor")
    public void executeAsync(String taskId) {
        log.info("Starting async route generation for task: {}", taskId);
        try {
            taskService.updateStatus(taskId, TaskStatus.PROCESSING);
            RouteTask task = taskService.getTask(taskId);

            double lat = task.getStartPoint().getY();
            double lng = task.getStartPoint().getX();
            boolean avoidMainRoad = Boolean.TRUE.equals(task.getAvoidMainRoad());
            boolean preferPark = Boolean.TRUE.equals(task.getPreferPark());

            // 1. Shape Engine
            log.info("[Pipeline 1/5] Generating shape coordinates via AI");
            List<AnchorPoint> anchorPoints = shapeEngineService.generateShapeCoordinates(
                    task.getRequestText(), task.getShapeType());

            // 2~5. 회전 변형으로 복수 후보 생성
            List<CandidateResult> candidates = new ArrayList<>();
            for (int i = 0; i < MAX_CANDIDATES; i++) {
                try {
                    double rotation = ROTATION_ANGLES[i];
                    log.info("[Candidate {}/{}] Generating with rotation={}°", i + 1, MAX_CANDIDATES, rotation);

                    List<AnchorPoint> rotated = (rotation == 0.0)
                            ? anchorPoints
                            : rotatePoints(anchorPoints, rotation);

                    CandidateResult result = buildCandidate(
                            task, rotated, lat, lng, avoidMainRoad, preferPark);
                    if (result != null) {
                        candidates.add(result);
                    }
                } catch (Exception e) {
                    log.warn("[Candidate {}/{}] Failed: {}", i + 1, MAX_CANDIDATES, e.getMessage());
                }
            }

            if (candidates.isEmpty()) {
                throw new RuntimeException("모든 후보 경로 생성에 실패했습니다.");
            }

            // 종합 점수로 정렬 후 저장
            candidates.sort(Comparator.comparingDouble(CandidateResult::compositeScore).reversed());
            for (int rank = 0; rank < candidates.size(); rank++) {
                CandidateResult c = candidates.get(rank);
                Route route = Route.builder()
                        .task(task)
                        .polyline(c.polyline())
                        .originalShape(c.originalShape())
                        .distanceMeters(c.distanceMeters())
                        .similarityScore(c.similarityScore())
                        .pedestrianRoadRatio(c.pedestrianRatio())
                        .ranking(rank + 1)
                        .build();
                routeRepository.save(route);
                log.info("Route #{} saved: distance={}m, similarity={:.1f}, composite={:.1f}",
                        rank + 1, (int) c.distanceMeters(), c.similarityScore(), c.compositeScore());
            }

            taskService.updateStatus(taskId, TaskStatus.COMPLETED);
            log.info("Route generation completed: {} candidates for task {}", candidates.size(), taskId);
        } catch (Exception e) {
            log.error("Route generation failed for task: {}", taskId, e);
            taskService.markFailed(taskId, e.getMessage());
        }
    }

    private CandidateResult buildCandidate(RouteTask task, List<AnchorPoint> points,
                                           double lat, double lng,
                                           boolean avoidMainRoad, boolean preferPark) {
        // 2. Geospatial Scale
        Coordinate[] scaledCoords = geospatialScaleService.scaleAndTranslate(
                points, lat, lng, task.getTargetDistanceKm());
        Geometry originalShape = geospatialScaleService.createGeometry(scaledCoords);

        // 2.5. Interpolation - 앵커 포인트 사이에 100m 간격으로 중간점 삽입
        Coordinate[] denseCoords = geospatialScaleService.interpolate(scaledCoords, 100.0);

        // 3. Map Matching - 촘촘한 점들을 도로에 스냅
        List<Long> nodeIds = mapMatchingService.snapToOsmNodes(denseCoords);

        // 4. Routing Engine
        LineString routePolyline = routingEngineService.buildRoute(nodeIds, avoidMainRoad, preferPark);
        double distanceMeters = routingEngineService.calculateRouteDistance(routePolyline);

        // 5. Validation & Scoring
        validationScoringService.validateRoute(routePolyline);
        double similarity = validationScoringService.calculateSimilarity(routePolyline, originalShape);
        double pedestrianRatio = validationScoringService.calculatePedestrianRoadRatio(routePolyline);
        double distanceAccuracy = validationScoringService.calculateDistanceAccuracy(
                distanceMeters, task.getTargetDistanceKm() * 1000.0);
        double compositeScore = validationScoringService.calculateCompositeScore(
                similarity, pedestrianRatio, distanceAccuracy);

        if (!validationScoringService.meetsMinimumQuality(similarity)) {
            log.warn("Candidate rejected: similarity={} below threshold", similarity);
            return null;
        }

        return new CandidateResult(routePolyline, originalShape, distanceMeters,
                similarity, pedestrianRatio, compositeScore);
    }

    private List<AnchorPoint> rotatePoints(List<AnchorPoint> points, double angleDegrees) {
        double rad = Math.toRadians(angleDegrees);
        double cos = Math.cos(rad);
        double sin = Math.sin(rad);
        return points.stream()
                .map(p -> new AnchorPoint(
                        p.getX() * cos - p.getY() * sin,
                        p.getX() * sin + p.getY() * cos))
                .toList();
    }

    private record CandidateResult(
            LineString polyline, Geometry originalShape, double distanceMeters,
            double similarityScore, double pedestrianRatio, double compositeScore) {}
}
