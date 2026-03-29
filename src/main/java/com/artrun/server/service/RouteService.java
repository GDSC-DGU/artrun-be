package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RouteTask;
import com.artrun.server.domain.TaskStatus;
import com.artrun.server.dto.request.RouteGenerateRequest;
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

@Slf4j
@Service
@RequiredArgsConstructor
public class RouteService {

    private final RouteTaskRepository routeTaskRepository;
    private final RouteRepository routeRepository;
    private final RouteGenerationOrchestrator orchestrator;

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

        // 트랜잭션 커밋 후 비동기 실행 (커밋 전 실행 시 task 조회 실패)
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                orchestrator.executeAsync(saved.getId());
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

        var builder = RouteStatusResponse.builder()
                .status(task.getStatus().name());

        if (task.getStatus() == TaskStatus.FAILED) {
            builder.errorMessage(task.getErrorMessage());
        }

        if (task.getStatus() == TaskStatus.COMPLETED) {
            List<Route> routes = routeRepository.findByTaskIdOrderByRankingAsc(taskId);
            List<CandidateRouteDto> candidates = routes.stream()
                    .map(this::toDto)
                    .toList();
            builder.candidateRoutes(candidates);
        }

        return builder.build();
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
