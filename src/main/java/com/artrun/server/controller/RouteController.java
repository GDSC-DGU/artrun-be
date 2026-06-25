package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.RegenerateRouteRequest;
import com.artrun.server.dto.request.RouteGenerateRequest;
import com.artrun.server.dto.response.RouteDetailResponse;
import com.artrun.server.dto.response.RouteStatusResponse;
import com.artrun.server.dto.response.TaskResponse;
import com.artrun.server.service.RouteService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@Tag(name = "Route", description = "GPS 아트 경로 생성 API")
@RestController
@RequestMapping("/api/v1/routes")
@RequiredArgsConstructor
public class RouteController {

    private final RouteService routeService;

    @Operation(summary = "러닝 루트 생성 요청 (비동기, taskId 반환)")
    @PostMapping("/generate")
    public ResponseEntity<ApiResponse<TaskResponse>> generateRoute(
            @Valid @RequestBody RouteGenerateRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.ok("경로 생성 작업이 시작되었습니다.", routeService.generateRoute(request)));
    }

    @Operation(summary = "루트 생성 상태 조회 (폴링)")
    @GetMapping("/status/{taskId}")
    public ResponseEntity<ApiResponse<RouteStatusResponse>> getStatus(
            @Parameter(description = "경로 생성 작업 ID") @PathVariable String taskId) {
        return ResponseEntity.ok(ApiResponse.ok(routeService.getTaskStatus(taskId)));
    }

    @Operation(summary = "루트 상세 조회 (체크포인트 포함)")
    @GetMapping("/{routeId}")
    public ResponseEntity<ApiResponse<RouteDetailResponse>> getRoute(
            @Parameter(description = "루트 ID") @PathVariable String routeId) {
        return ResponseEntity.ok(ApiResponse.ok(routeService.getRoute(routeId)));
    }

    @Operation(summary = "루트 재생성 요청 (기존 조건 기반)")
    @PostMapping("/{routeId}/regenerate")
    public ResponseEntity<ApiResponse<TaskResponse>> regenerateRoute(
            @Parameter(description = "기존 루트 ID") @PathVariable String routeId,
            @RequestBody(required = false) RegenerateRouteRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.ok("경로 재생성 작업이 시작되었습니다.", routeService.regenerateRoute(routeId, request)));
    }
}
