package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.StartSessionRequest;
import com.artrun.server.dto.request.TrackRequest;
import com.artrun.server.dto.request.CancelSessionRequest;
import com.artrun.server.dto.request.FinishSessionRequest;
import com.artrun.server.dto.request.ResumeSessionRequest;
import com.artrun.server.dto.response.CancelSessionResponse;
import com.artrun.server.dto.response.FinishSessionResponse;
import com.artrun.server.dto.response.PauseSessionResponse;
import com.artrun.server.dto.response.ResumeSessionResponse;
import com.artrun.server.dto.response.SessionDetailResponse;
import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.dto.response.StartSessionResponse;
import com.artrun.server.dto.response.TrackResponse;
import com.artrun.server.security.CustomUserDetails;
import com.artrun.server.service.SessionService;
import com.artrun.server.service.TrackingService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@Tag(name = "Session", description = "러닝 세션 관리 API")
@RestController
@RequestMapping("/api/v1/session")
@RequiredArgsConstructor
public class SessionController {

    private final TrackingService trackingService;
    private final SessionService sessionService;

    @Operation(summary = "러닝 세션 시작")
    @PostMapping("/start")
    public ResponseEntity<ApiResponse<StartSessionResponse>> startSession(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody StartSessionRequest request) {
        StartSessionResponse response = sessionService.startSession(userDetails.getUserId(), request);
        if (!response.isStartAllowed()) {
            return ResponseEntity.ok(
                    ApiResponse.fail("루트 시작점에서 너무 멀리 떨어져 있습니다.", response));
        }
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.ok("러닝 세션이 시작되었습니다.", response));
    }

    @Operation(summary = "실시간 위치 검증 및 러닝 안내 (1~3초 간격 호출)")
    @PostMapping("/{sessionId}/track")
    public ResponseEntity<ApiResponse<TrackResponse>> track(
            @Parameter(description = "세션 ID") @PathVariable String sessionId,
            @Valid @RequestBody TrackRequest request) {
        TrackResponse response = trackingService.checkPosition(sessionId, request);
        return ResponseEntity.ok(ApiResponse.ok("위치 검증 성공", response));
    }

    @Operation(summary = "러닝 세션 일시정지")
    @PostMapping("/{sessionId}/pause")
    public ResponseEntity<ApiResponse<PauseSessionResponse>> pause(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String sessionId) {
        PauseSessionResponse response = sessionService.pauseSession(userDetails.getUserId(), sessionId);
        return ResponseEntity.ok(ApiResponse.ok("러닝 세션이 일시정지되었습니다.", response));
    }

    @Operation(summary = "러닝 세션 재개")
    @PostMapping("/{sessionId}/resume")
    public ResponseEntity<ApiResponse<ResumeSessionResponse>> resume(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String sessionId,
            @Valid @RequestBody ResumeSessionRequest request) {
        ResumeSessionResponse response = sessionService.resumeSession(userDetails.getUserId(), sessionId, request);
        return ResponseEntity.ok(ApiResponse.ok("러닝 세션이 재개되었습니다.", response));
    }

    @Operation(summary = "러닝 세션 종료 (기록 저장 준비 상태로 전환)")
    @PostMapping("/{sessionId}/finish")
    public ResponseEntity<ApiResponse<FinishSessionResponse>> finish(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String sessionId,
            @RequestBody(required = false) FinishSessionRequest request) {
        FinishSessionResponse response = sessionService.finishSession(
                userDetails.getUserId(), sessionId, request != null ? request : new FinishSessionRequest());
        return ResponseEntity.ok(ApiResponse.ok("러닝 세션이 종료되었습니다.", response));
    }

    @Operation(summary = "러닝 세션 취소")
    @PostMapping("/{sessionId}/cancel")
    public ResponseEntity<ApiResponse<CancelSessionResponse>> cancel(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String sessionId,
            @RequestBody(required = false) CancelSessionRequest request) {
        CancelSessionResponse response = sessionService.cancelSession(userDetails.getUserId(), sessionId, request);
        return ResponseEntity.ok(ApiResponse.ok("러닝 세션이 취소되었습니다.", response));
    }

    @Operation(summary = "러닝 세션 상태 조회 (앱 재진입/네트워크 복구 시)")
    @GetMapping("/{sessionId}")
    public ResponseEntity<ApiResponse<SessionDetailResponse>> getSession(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String sessionId) {
        return ResponseEntity.ok(ApiResponse.ok("러닝 세션 상태 조회 성공", sessionService.getSession(userDetails.getUserId(), sessionId)));
    }

    // WebSocket STOMP 엔드포인트
    @MessageMapping("/session/{sessionId}/track")
    @SendTo("/topic/session/{sessionId}")
    public TrackResponse trackWebSocket(@DestinationVariable String sessionId, TrackRequest request) {
        return trackingService.checkPosition(sessionId, request);
    }
}
