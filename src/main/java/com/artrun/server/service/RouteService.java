package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RouteTask;
import com.artrun.server.domain.TaskStatus;
import com.artrun.server.dto.request.RegenerateRouteRequest;
import com.artrun.server.dto.request.RouteGenerateRequest;
import com.artrun.server.dto.response.RouteDetailResponse;
import com.artrun.server.dto.response.RouteStatusResponse;
import com.artrun.server.dto.response.RouteStatusResponse.CandidateRouteDto;
import com.artrun.server.dto.response.TaskResponse;
import com.artrun.server.repository.RouteRepository;
import com.artrun.server.repository.RouteTaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.Point;
import org.locationtech.jts.geom.PrecisionModel;
import org.locationtech.jts.operation.distance.DistanceOp;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.RejectedExecutionException;

@Slf4j
@Service
@RequiredArgsConstructor
public class RouteService {

    private final RouteTaskRepository routeTaskRepository;
    private final RouteRepository routeRepository;
    private final RouteGenerationOrchestrator orchestrator;
    private final TaskService taskService;

    private static final GeometryFactory GEOMETRY_FACTORY = new GeometryFactory(new PrecisionModel(), 4326);

    @Transactional
    public TaskResponse generateRoute(RouteGenerateRequest request) {
        Point startPoint = GEOMETRY_FACTORY.createPoint(
                new Coordinate(request.getStartPoint().getLng(), request.getStartPoint().getLat()));

        var preferences = request.getPreferences();

        RouteTask task = RouteTask.builder()
                .status(TaskStatus.PENDING)
                .requestText(request.getRequestText())
                .shapeType(request.getShapeType())
                .activityType(request.getActivityType())
                .targetDistanceKm(request.getTargetDistanceKm())
                .targetPaceSecPerKm(request.getTargetPaceSecPerKm())
                .startAddressName(request.getStartPoint().getAddressName())
                .startPoint(startPoint)
                .avoidMainRoad(preferences != null && preferences.isAvoidMainRoad())
                .preferPark(preferences != null && preferences.isPreferPark())
                .avoidStairs(preferences != null && preferences.isAvoidStairs())
                .preferWaterfront(preferences != null && preferences.isPreferWaterfront())
                .maxSlopeLevel(preferences != null ? preferences.getMaxSlopeLevel() : null)
                .build();

        RouteTask saved = routeTaskRepository.save(task);

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                try {
                    orchestrator.executeAsync(saved.getId());
                } catch (RejectedExecutionException e) {
                    log.error("Route generation queue is full, task {} will be marked as FAILED", saved.getId());
                    taskService.markFailed(saved.getId(), "서버 처리 대기열이 가득 찼습니다. 잠시 후 다시 시도해주세요.");
                }
            }
        });

        return TaskResponse.builder()
                .taskId(saved.getId())
                .status(TaskStatus.PENDING.name())
                .estimatedSeconds(15)
                .build();
    }

    @Transactional(readOnly = true)
    public RouteStatusResponse getTaskStatus(String taskId) {
        RouteTask task = routeTaskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TASK_NOT_FOUND));

        TaskStatus status = task.getStatus();
        var builder = RouteStatusResponse.builder()
                .status(status.name())
                .progressRate(computeProgressRate(status));

        if (status == TaskStatus.FAILED) {
            builder.errorMessage(task.getErrorMessage());
        }
        if (status == TaskStatus.COMPLETED) {
            List<Route> routes = routeRepository.findByTaskIdOrderByRankingAsc(taskId);
            builder.candidateRoutes(routes.stream().map(this::toDto).toList());
        }

        return builder.build();
    }

    @Transactional(readOnly = true)
    public RouteDetailResponse getRoute(String routeId) {
        Route route = routeRepository.findById(routeId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ROUTE_NOT_FOUND));

        RouteTask task = route.getTask();

        List<RouteDetailResponse.PolylinePoint> polylinePoints = route.getPolyline() != null
                ? buildPolylinePoints(route.getPolyline().getCoordinates())
                : List.of();

        List<RouteDetailResponse.LatLng> latLngs = polylinePoints.stream()
                .map(p -> RouteDetailResponse.LatLng.builder().lat(p.getLat()).lng(p.getLng()).build())
                .toList();

        RouteDetailResponse.LatLng startPoint = resolveStartPoint(route, latLngs);
        RouteDetailResponse.LatLng endPoint = latLngs.isEmpty() ? null : latLngs.get(latLngs.size() - 1);

        String activityType = task != null ? task.getActivityType() : null;
        double distanceMeters = route.getDistanceMeters() != null ? route.getDistanceMeters() : 0.0;
        double distanceKm = Math.round(distanceMeters / 10.0) / 100.0;
        int pace = (task != null && task.getTargetPaceSecPerKm() != null)
                ? task.getTargetPaceSecPerKm()
                : resolvePace(activityType);
        int estimatedTimeSeconds = (int) (distanceKm * pace);

        return RouteDetailResponse.builder()
                .routeId(route.getId())
                .routeName(route.getRouteName())
                .shapeType(task != null ? task.getShapeType() : null)
                .activityType(activityType)
                .distanceKm(distanceKm)
                .estimatedTimeSeconds(estimatedTimeSeconds)
                .targetPaceSecPerKm(pace)
                .similarityScore(route.getSimilarityScore() != null ? route.getSimilarityScore().intValue() : null)
                .pedestrianRoadRatio(route.getPedestrianRoadRatio() != null ? route.getPedestrianRoadRatio().intValue() : null)
                .expectedBpm(resolveBpm(activityType))
                .startPoint(startPoint)
                .endPoint(endPoint)
                .bounds(computeBounds(latLngs))
                .polyline(polylinePoints)
                .checkpoints(buildCheckpoints(latLngs))
                .turnInstructions(buildTurnInstructions(latLngs))
                .previewImageUrl(route.getPreviewImageUrl())
                .createdAt(route.getCreatedAt())
                .build();
    }

    @Transactional
    public TaskResponse regenerateRoute(String routeId, RegenerateRouteRequest request) {
        Route original = routeRepository.findById(routeId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ROUTE_NOT_FOUND));

        RouteTask originalTask = original.getTask();
        RouteGenerateRequest.PreferencesDto prefs = (request != null) ? request.getPreferences() : null;

        RouteTask newTask = RouteTask.builder()
                .status(TaskStatus.PENDING)
                .requestText(originalTask.getRequestText())
                .shapeType(originalTask.getShapeType())
                .activityType(originalTask.getActivityType())
                .targetDistanceKm(originalTask.getTargetDistanceKm())
                .targetPaceSecPerKm(originalTask.getTargetPaceSecPerKm())
                .startAddressName(originalTask.getStartAddressName())
                .startPoint(originalTask.getStartPoint())
                .avoidMainRoad(prefs != null ? prefs.isAvoidMainRoad() : Boolean.TRUE.equals(originalTask.getAvoidMainRoad()))
                .preferPark(prefs != null ? prefs.isPreferPark() : Boolean.TRUE.equals(originalTask.getPreferPark()))
                .avoidStairs(prefs != null ? prefs.isAvoidStairs() : Boolean.TRUE.equals(originalTask.getAvoidStairs()))
                .preferWaterfront(prefs != null ? prefs.isPreferWaterfront() : Boolean.TRUE.equals(originalTask.getPreferWaterfront()))
                .maxSlopeLevel(prefs != null ? prefs.getMaxSlopeLevel() : originalTask.getMaxSlopeLevel())
                .build();

        RouteTask saved = routeTaskRepository.save(newTask);

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                try {
                    orchestrator.executeAsync(saved.getId());
                } catch (RejectedExecutionException e) {
                    taskService.markFailed(saved.getId(), "서버 처리 대기열이 가득 찼습니다.");
                }
            }
        });

        return TaskResponse.builder()
                .taskId(saved.getId())
                .status(TaskStatus.PENDING.name())
                .estimatedSeconds(15)
                .build();
    }

    private List<RouteDetailResponse.PolylinePoint> buildPolylinePoints(Coordinate[] coords) {
        List<RouteDetailResponse.PolylinePoint> points = new ArrayList<>(coords.length);
        for (int i = 0; i < coords.length; i++) {
            points.add(RouteDetailResponse.PolylinePoint.builder()
                    .lat(coords[i].y)
                    .lng(coords[i].x)
                    .order(i + 1)
                    .build());
        }
        return points;
    }

    private RouteDetailResponse.LatLng resolveStartPoint(Route route, List<RouteDetailResponse.LatLng> polyline) {
        if (polyline.isEmpty()) return null;
        Point requestedStart = route.getTask() != null ? route.getTask().getStartPoint() : null;
        if (requestedStart == null || route.getPolyline() == null) return polyline.get(0);
        Coordinate nearest = DistanceOp.nearestPoints(route.getPolyline(), requestedStart)[0];
        return RouteDetailResponse.LatLng.builder().lat(nearest.y).lng(nearest.x).build();
    }

    private RouteDetailResponse.Bounds computeBounds(List<RouteDetailResponse.LatLng> points) {
        if (points.isEmpty()) return null;
        double minLat = points.stream().mapToDouble(RouteDetailResponse.LatLng::getLat).min().orElse(0);
        double maxLat = points.stream().mapToDouble(RouteDetailResponse.LatLng::getLat).max().orElse(0);
        double minLng = points.stream().mapToDouble(RouteDetailResponse.LatLng::getLng).min().orElse(0);
        double maxLng = points.stream().mapToDouble(RouteDetailResponse.LatLng::getLng).max().orElse(0);
        return RouteDetailResponse.Bounds.builder()
                .northEast(RouteDetailResponse.LatLng.builder().lat(maxLat).lng(maxLng).build())
                .southWest(RouteDetailResponse.LatLng.builder().lat(minLat).lng(minLng).build())
                .build();
    }

    private List<RouteDetailResponse.CheckpointDto> buildCheckpoints(List<RouteDetailResponse.LatLng> polyline) {
        if (polyline.size() < 2) return List.of();
        double[] cumDist = computeCumulativeDistances(polyline);
        int step = Math.max(1, polyline.size() / 10);
        List<RouteDetailResponse.CheckpointDto> result = new ArrayList<>();
        int seq = 1;
        for (int i = 0; i < polyline.size(); i++) {
            if (i % step != 0 && i != polyline.size() - 1) continue;
            boolean isFirst = (seq == 1);
            boolean isLast = (i == polyline.size() - 1);
            String name = isFirst ? "출발 지점" : isLast ? "도착 지점" : "경유 지점 " + (seq - 1);
            String description = isFirst ? "러닝을 시작합니다." : isLast ? "러닝이 완료되었습니다." : "경유 지점에 도착했습니다.";
            result.add(RouteDetailResponse.CheckpointDto.builder()
                    .checkpointId("cp_" + seq)
                    .sequence(seq)
                    .name(name)
                    .description(description)
                    .distanceFromStartMeters((int) cumDist[i])
                    .point(polyline.get(i))
                    .build());
            seq++;
        }
        return result;
    }

    private List<RouteDetailResponse.TurnInstructionDto> buildTurnInstructions(List<RouteDetailResponse.LatLng> polyline) {
        if (polyline.size() < 3) return List.of();
        double[] cumDist = computeCumulativeDistances(polyline);
        List<RouteDetailResponse.TurnInstructionDto> result = new ArrayList<>();
        int seq = 1;
        for (int i = 1; i < polyline.size() - 1; i++) {
            RouteDetailResponse.LatLng prev = polyline.get(i - 1);
            RouteDetailResponse.LatLng curr = polyline.get(i);
            RouteDetailResponse.LatLng next = polyline.get(i + 1);
            double b1 = bearing(prev.getLat(), prev.getLng(), curr.getLat(), curr.getLng());
            double b2 = bearing(curr.getLat(), curr.getLng(), next.getLat(), next.getLng());
            double turn = angleDiff(b1, b2);
            if (Math.abs(turn) < 30) continue;
            String type = turn > 0 ? "RIGHT" : "LEFT";
            int nextDist = (int) haversineMeters(curr.getLat(), curr.getLng(), next.getLat(), next.getLng());
            String direction = turn > 0 ? "우회전" : "좌회전";
            result.add(RouteDetailResponse.TurnInstructionDto.builder()
                    .instructionId("turn_" + seq)
                    .sequence(seq)
                    .type(type)
                    .message(String.format("%dm 앞에서 %s하세요.", nextDist, direction))
                    .distanceFromStartMeters((int) cumDist[i])
                    .nextDistanceMeters(nextDist)
                    .point(curr)
                    .build());
            seq++;
        }
        return result;
    }

    private double[] computeCumulativeDistances(List<RouteDetailResponse.LatLng> polyline) {
        double[] distances = new double[polyline.size()];
        for (int i = 1; i < polyline.size(); i++) {
            RouteDetailResponse.LatLng p1 = polyline.get(i - 1);
            RouteDetailResponse.LatLng p2 = polyline.get(i);
            distances[i] = distances[i - 1] + haversineMeters(p1.getLat(), p1.getLng(), p2.getLat(), p2.getLng());
        }
        return distances;
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

    private int resolvePace(String activityType) {
        if (activityType == null) return 330;
        return switch (activityType.toUpperCase()) {
            case "WALKING" -> 600;
            case "CYCLING" -> 150;
            default -> 330;
        };
    }

    private int resolveBpm(String activityType) {
        if (activityType == null) return 156;
        return switch (activityType.toUpperCase()) {
            case "WALKING" -> 100;
            case "CYCLING" -> 130;
            default -> 156;
        };
    }

    private CandidateRouteDto toDto(Route route) {
        RouteTask task = route.getTask();

        List<RouteDetailResponse.PolylinePoint> polylinePoints = route.getPolyline() != null
                ? buildPolylinePoints(route.getPolyline().getCoordinates())
                : List.of();

        List<RouteDetailResponse.LatLng> latLngs = polylinePoints.stream()
                .map(p -> RouteDetailResponse.LatLng.builder().lat(p.getLat()).lng(p.getLng()).build())
                .toList();

        String activityType = task != null ? task.getActivityType() : null;
        double distanceMeters = route.getDistanceMeters() != null ? route.getDistanceMeters() : 0.0;
        double distanceKm = Math.round(distanceMeters / 10.0) / 100.0;
        int pace = (task != null && task.getTargetPaceSecPerKm() != null)
                ? task.getTargetPaceSecPerKm()
                : resolvePace(activityType);

        return CandidateRouteDto.builder()
                .routeId(route.getId())
                .routeName(route.getRouteName())
                .shapeType(task != null ? task.getShapeType() : null)
                .activityType(activityType)
                .distanceKm(distanceKm)
                .estimatedTimeSeconds((int) (distanceKm * pace))
                .targetPaceSecPerKm(pace)
                .similarityScore(route.getSimilarityScore() != null ? route.getSimilarityScore().intValue() : null)
                .pedestrianRoadRatio(route.getPedestrianRoadRatio() != null ? route.getPedestrianRoadRatio().intValue() : null)
                .expectedBpm(resolveBpm(activityType))
                .startPoint(resolveStartPoint(route, latLngs))
                .endPoint(latLngs.isEmpty() ? null : latLngs.get(latLngs.size() - 1))
                .bounds(computeBounds(latLngs))
                .polyline(polylinePoints)
                .checkpoints(buildCheckpoints(latLngs))
                .turnInstructions(buildTurnInstructions(latLngs))
                .previewImageUrl(route.getPreviewImageUrl())
                .warnings(List.of())
                .build();
    }

    private int computeProgressRate(TaskStatus status) {
        return switch (status) {
            case PENDING -> 0;
            case PROCESSING -> 50;
            case COMPLETED -> 100;
            case FAILED -> 0;
        };
    }
}
