package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.StartSessionRequest;
import com.artrun.server.dto.request.TrackRequest;
import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.dto.response.TrackResponse;
import com.artrun.server.service.SessionService;
import com.artrun.server.service.TrackingService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.web.bind.annotation.*;

@Tag(name = "Session", description = "러닝 세션 관리 및 실시간 위치 추적 API")
@RestController
@RequiredArgsConstructor
public class SessionController {

    private final TrackingService trackingService;
    private final SessionService sessionService;

    @Operation(summary = "러닝 세션 시작", description = "선택한 경로로 러닝 세션을 생성하고 시작합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "201", description = "세션 생성 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "경로를 찾을 수 없음")
    })
    @PostMapping("/api/v1/session/start")
    public ResponseEntity<ApiResponse<SessionResponse>> startSession(
            @Valid @RequestBody StartSessionRequest request) {
        SessionResponse response = sessionService.startSession(request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.ok("러닝 세션이 시작되었습니다.", response));
    }

    @Operation(summary = "실시간 위치 검증", description = "러닝 중 현재 GPS 위치를 전송하여 경로 이탈 여부와 남은 거리를 확인합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "위치 검증 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "세션을 찾을 수 없음")
    })
    @PostMapping("/api/v1/session/{sessionId}/track")
    public ResponseEntity<ApiResponse<TrackResponse>> track(
            @Parameter(description = "러닝 세션 ID") @PathVariable String sessionId,
            @Valid @RequestBody TrackRequest request) {
        TrackResponse response = trackingService.checkPosition(
                sessionId, request.getLat(), request.getLng());
        return ResponseEntity.ok(ApiResponse.ok(response));
    }

    // WebSocket STOMP 엔드포인트
    @MessageMapping("/session/{sessionId}/track")
    @SendTo("/topic/session/{sessionId}")
    public TrackResponse trackWebSocket(
            @DestinationVariable String sessionId,
            TrackRequest request) {
        return trackingService.checkPosition(sessionId, request.getLat(), request.getLng());
    }
}
