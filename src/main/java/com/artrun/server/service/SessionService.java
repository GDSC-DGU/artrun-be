package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import com.artrun.server.dto.request.StartSessionRequest;
import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.repository.RouteRepository;
import com.artrun.server.repository.RunSessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class SessionService {

    private final RunSessionRepository runSessionRepository;
    private final RouteRepository routeRepository;

    @Transactional
    public SessionResponse startSession(StartSessionRequest request) {
        Route route = routeRepository.findById(request.getRouteId())
                .orElseThrow(() -> new BusinessException(ErrorCode.ROUTE_NOT_FOUND));

        RunSession session = RunSession.builder()
                .route(route)
                .status(SessionStatus.ACTIVE)
                .startedAt(LocalDateTime.now())
                .build();

        RunSession saved = runSessionRepository.save(session);
        log.info("Session started: sessionId={}, routeId={}", saved.getId(), request.getRouteId());

        return SessionResponse.builder()
                .sessionId(saved.getId())
                .routeId(request.getRouteId())
                .status(SessionStatus.ACTIVE.name())
                .message("러닝 세션이 시작되었습니다.")
                .build();
    }
}
