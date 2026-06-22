package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import com.artrun.server.domain.User;
import com.artrun.server.dto.request.StartSessionRequest;
import com.artrun.server.dto.response.SessionDetailResponse;
import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.repository.RouteRepository;
import com.artrun.server.repository.RunSessionRepository;
import com.artrun.server.repository.UserRepository;
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
    private final UserRepository userRepository;

    @Transactional
    public SessionResponse startSession(String userId, StartSessionRequest request) {
        Route route = routeRepository.findById(request.getRouteId())
                .orElseThrow(() -> new BusinessException(ErrorCode.ROUTE_NOT_FOUND));

        if (runSessionRepository.existsByUser_IdAndRoute_IdAndStatus(userId, request.getRouteId(), SessionStatus.ACTIVE)) {
            throw new BusinessException(ErrorCode.SESSION_ALREADY_ACTIVE);
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        RunSession session = RunSession.builder()
                .user(user)
                .route(route)
                .status(SessionStatus.ACTIVE)
                .startedAt(LocalDateTime.now())
                .build();

        RunSession saved = runSessionRepository.save(session);
        log.info("Session started: sessionId={}, routeId={}, userId={}", saved.getId(), request.getRouteId(), userId);

        return SessionResponse.builder()
                .sessionId(saved.getId())
                .routeId(request.getRouteId())
                .status(SessionStatus.ACTIVE.name())
                .message("러닝 세션이 시작되었습니다.")
                .build();
    }

    @Transactional
    public void pauseSession(String userId, String sessionId) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() != SessionStatus.ACTIVE) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.PAUSED);
        runSessionRepository.save(session);
    }

    @Transactional
    public void resumeSession(String userId, String sessionId) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() != SessionStatus.PAUSED) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.ACTIVE);
        runSessionRepository.save(session);
    }

    @Transactional
    public SessionResponse finishSession(String userId, String sessionId) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() != SessionStatus.ACTIVE && session.getStatus() != SessionStatus.PAUSED) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.FINISHED);
        session.setFinishedAt(LocalDateTime.now());
        RunSession saved = runSessionRepository.save(session);

        return SessionResponse.builder()
                .sessionId(saved.getId())
                .routeId(saved.getRoute().getId())
                .status(SessionStatus.FINISHED.name())
                .message("러닝이 종료되었습니다. 기록을 저장해주세요.")
                .build();
    }

    @Transactional
    public void cancelSession(String userId, String sessionId) {
        RunSession session = getOwnedSession(userId, sessionId);
        if (session.getStatus() == SessionStatus.COMPLETED || session.getStatus() == SessionStatus.CANCELLED) {
            throw new BusinessException(ErrorCode.SESSION_INACTIVE);
        }
        session.setStatus(SessionStatus.CANCELLED);
        runSessionRepository.save(session);
    }

    @Transactional(readOnly = true)
    public SessionDetailResponse getSession(String userId, String sessionId) {
        RunSession session = getOwnedSession(userId, sessionId);
        return SessionDetailResponse.builder()
                .sessionId(session.getId())
                .routeId(session.getRoute().getId())
                .status(session.getStatus().name())
                .startedAt(session.getStartedAt())
                .finishedAt(session.getFinishedAt())
                .build();
    }

    private RunSession getOwnedSession(String userId, String sessionId) {
        return runSessionRepository.findByIdAndUser_Id(sessionId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.SESSION_NOT_FOUND));
    }
}
