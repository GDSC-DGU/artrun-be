package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.TrackRequest;
import com.artrun.server.dto.response.TrackResponse;
import com.artrun.server.service.TrackingService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
public class SessionController {

    private final TrackingService trackingService;

    @PostMapping("/api/v1/session/{sessionId}/track")
    public ResponseEntity<ApiResponse<TrackResponse>> track(
            @PathVariable String sessionId,
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
