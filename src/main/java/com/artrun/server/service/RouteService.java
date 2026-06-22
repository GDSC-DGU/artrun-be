package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RouteTask;
import com.artrun.server.domain.TaskStatus;
import com.artrun.server.dto.request.RouteGenerateRequest;
import com.artrun.server.dto.response.RouteDetailResponse;
import com.artrun.server.dto.response.RouteStatusResponse;
import com.artrun.server.dto.response.RouteStatusResponse.CandidateRouteDto;
import com.artrun.server.dto.response.RouteStatusResponse.LatLng;
import com.artrun.server.dto.response.TaskResponse;
import com.artrun.server.repository.RouteRepository;
import com.artrun.server.repository.RouteTaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.Point;
import org.locationtech.jts.geom.PrecisionModel;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.Arrays;
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
                .startPoint(startPoint)
                .avoidMainRoad(preferences != null && preferences.isAvoidMainRoad())
                .preferPark(preferences != null && preferences.isPreferPark())
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
                .message("경로 생성을 시작합니다. 상태 조회 API를 호출해주세요.")
                .build();
    }

    @Transactional(readOnly = true)
    public RouteStatusResponse getTaskStatus(String taskId) {
        RouteTask task = routeTaskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TASK_NOT_FOUND));

        var builder = RouteStatusResponse.builder().status(task.getStatus().name());

        if (task.getStatus() == TaskStatus.FAILED) {
            builder.errorMessage(task.getErrorMessage());
        }
        if (task.getStatus() == TaskStatus.COMPLETED) {
            List<Route> routes = routeRepository.findByTaskIdOrderByRankingAsc(taskId);
            builder.candidateRoutes(routes.stream().map(this::toDto).toList());
        }

        return builder.build();
    }

    @Transactional(readOnly = true)
    public RouteDetailResponse getRoute(String routeId) {
        Route route = routeRepository.findById(routeId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ROUTE_NOT_FOUND));

        List<RouteDetailResponse.LatLng> polyline = route.getPolyline() != null
                ? Arrays.stream(route.getPolyline().getCoordinates())
                    .map(c -> RouteDetailResponse.LatLng.builder().lat(c.y).lng(c.x).build())
                    .toList()
                : List.of();

        // 체크포인트: 전체 좌표 중 일정 간격으로 추출 (10% 단위)
        List<RouteDetailResponse.LatLng> checkpoints = extractCheckpoints(polyline);

        return RouteDetailResponse.builder()
                .routeId(route.getId())
                .distanceMeters(route.getDistanceMeters() != null ? route.getDistanceMeters() : 0)
                .similarityScore(route.getSimilarityScore())
                .pedestrianRoadRatio(route.getPedestrianRoadRatio())
                .polyline(polyline)
                .checkpoints(checkpoints)
                .build();
    }

    @Transactional
    public TaskResponse regenerateRoute(String routeId) {
        Route original = routeRepository.findById(routeId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ROUTE_NOT_FOUND));

        RouteTask originalTask = original.getTask();

        RouteTask newTask = RouteTask.builder()
                .status(TaskStatus.PENDING)
                .requestText(originalTask.getRequestText())
                .shapeType(originalTask.getShapeType())
                .activityType(originalTask.getActivityType())
                .targetDistanceKm(originalTask.getTargetDistanceKm())
                .startPoint(originalTask.getStartPoint())
                .avoidMainRoad(originalTask.getAvoidMainRoad())
                .preferPark(originalTask.getPreferPark())
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
                .message("새로운 경로 생성을 시작합니다.")
                .build();
    }

    private List<RouteDetailResponse.LatLng> extractCheckpoints(List<RouteDetailResponse.LatLng> polyline) {
        if (polyline.size() < 2) return polyline;
        int step = Math.max(1, polyline.size() / 10);
        return java.util.stream.IntStream.range(0, polyline.size())
                .filter(i -> i % step == 0 || i == polyline.size() - 1)
                .mapToObj(polyline::get)
                .toList();
    }

    private CandidateRouteDto toDto(Route route) {
        List<LatLng> polyline = route.getPolyline() != null
                ? Arrays.stream(route.getPolyline().getCoordinates())
                    .map(c -> new LatLng(c.y, c.x))
                    .toList()
                : List.of();

        return CandidateRouteDto.builder()
                .routeId(route.getId())
                .distance(route.getDistanceMeters())
                .similarityScore(route.getSimilarityScore())
                .pedestrianRoadRatio(route.getPedestrianRoadRatio())
                .polyline(polyline)
                .build();
    }
}
