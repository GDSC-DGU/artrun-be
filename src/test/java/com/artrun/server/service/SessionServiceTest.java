package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.domain.Route;
import com.artrun.server.domain.RunSession;
import com.artrun.server.domain.SessionStatus;
import com.artrun.server.dto.request.StartSessionRequest;
import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.repository.RouteRepository;
import com.artrun.server.repository.RunSessionRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SessionServiceTest {

    @Mock
    private RunSessionRepository runSessionRepository;

    @Mock
    private RouteRepository routeRepository;

    @InjectMocks
    private SessionService sessionService;

    @Test
    @DisplayName("유효한 routeId로 세션을 시작한다")
    void startSession_success() {
        Route route = Route.builder().id("route-1").build();
        RunSession session = RunSession.builder()
                .id("session-1").route(route).status(SessionStatus.ACTIVE).build();

        when(routeRepository.findById("route-1")).thenReturn(Optional.of(route));
        when(runSessionRepository.save(any())).thenReturn(session);

        SessionResponse response = sessionService.startSession(new StartSessionRequest("route-1"));

        assertThat(response.getSessionId()).isEqualTo("session-1");
        assertThat(response.getStatus()).isEqualTo("ACTIVE");
    }

    @Test
    @DisplayName("존재하지 않는 routeId면 예외를 던진다")
    void startSession_routeNotFound() {
        when(routeRepository.findById("invalid")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> sessionService.startSession(new StartSessionRequest("invalid")))
                .isInstanceOf(BusinessException.class);
    }
}
