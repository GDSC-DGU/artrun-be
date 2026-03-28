package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.RouteGenerateRequest;
import com.artrun.server.dto.response.RouteStatusResponse;
import com.artrun.server.dto.response.TaskResponse;
import com.artrun.server.service.RouteService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/routes")
@RequiredArgsConstructor
public class RouteController {

    private final RouteService routeService;

    @PostMapping("/generate")
    public ResponseEntity<ApiResponse<TaskResponse>> generateRoute(
            @Valid @RequestBody RouteGenerateRequest request) {
        TaskResponse response = routeService.generateRoute(request);
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.ok("경로 생성을 시작합니다.", response));
    }

    @GetMapping("/status/{taskId}")
    public ResponseEntity<ApiResponse<RouteStatusResponse>> getStatus(@PathVariable String taskId) {
        RouteStatusResponse response = routeService.getTaskStatus(taskId);
        return ResponseEntity.ok(ApiResponse.ok(response));
    }
}
