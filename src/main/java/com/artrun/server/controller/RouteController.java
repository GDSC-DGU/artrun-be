package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.RouteGenerateRequest;
import com.artrun.server.dto.response.RouteStatusResponse;
import com.artrun.server.dto.response.TaskResponse;
import com.artrun.server.service.RouteService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
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

    @Operation(summary = "경로 생성 요청", description = "사용자의 위치, 도형, 목표 거리를 받아 AI 기반 러닝 경로를 비동기로 생성합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "202", description = "경로 생성 작업이 시작됨"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "잘못된 요청")
    })
    @PostMapping("/generate")
    public ResponseEntity<ApiResponse<TaskResponse>> generateRoute(
            @Valid @RequestBody RouteGenerateRequest request) {
        TaskResponse response = routeService.generateRoute(request);
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.ok("경로 생성을 시작합니다.", response));
    }

    @Operation(summary = "경로 생성 상태 조회", description = "taskId로 경로 생성 작업의 진행 상태를 조회합니다. 완료 시 후보 경로 목록을 반환합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "상태 조회 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "작업을 찾을 수 없음")
    })
    @GetMapping("/status/{taskId}")
    public ResponseEntity<ApiResponse<RouteStatusResponse>> getStatus(
            @Parameter(description = "경로 생성 작업 ID") @PathVariable String taskId) {
        RouteStatusResponse response = routeService.getTaskStatus(taskId);
        return ResponseEntity.ok(ApiResponse.ok(response));
    }
}
