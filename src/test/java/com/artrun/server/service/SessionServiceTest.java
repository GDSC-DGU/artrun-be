package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.domain.*;
import com.artrun.server.dto.request.StartSessionRequest;
import com.artrun.server.dto.response.SessionDetailResponse;
import com.artrun.server.dto.response.SessionResponse;
import com.artrun.server.repository.RouteRepository;
import com.artrun.server.repository.RunSessionRepository;
import com.artrun.server.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class SessionServiceTest {

    @Mock RunSessionRepository runSessionRepository;
    @Mock RouteRepository routeRepository;
    @Mock UserRepository userRepository;

    @InjectMocks SessionService sessionService;

    private User mockUser() {
        return User.builder().id("user-1").email("test@test.com")
                .nickname("테스터").provider(AuthProvider.EMAIL).build();
    }

    private Route mockRoute(String id) {
        return Route.builder().id(id).build();
    }

    @Test
    @DisplayName("유효한 routeId로 세션을 시작한다")
    void startSession_success() {
        User user = mockUser();
        Route route = mockRoute("route-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user).route(route).status(SessionStatus.ACTIVE).build();

        when(routeRepository.findById("route-1")).thenReturn(Optional.of(route));
        when(runSessionRepository.existsByUser_IdAndRoute_IdAndStatus("user-1", "route-1", SessionStatus.ACTIVE)).thenReturn(false);
        when(userRepository.findById("user-1")).thenReturn(Optional.of(user));
        when(runSessionRepository.save(any())).thenReturn(session);

        SessionResponse response = sessionService.startSession("user-1", new StartSessionRequest("route-1"));

        assertThat(response.getSessionId()).isEqualTo("session-1");
        assertThat(response.getStatus()).isEqualTo("ACTIVE");
    }

    @Test
    @DisplayName("존재하지 않는 routeId면 예외를 던진다")
    void startSession_routeNotFound() {
        when(routeRepository.findById("invalid")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> sessionService.startSession("user-1", new StartSessionRequest("invalid")))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("이미 활성 세션이 있으면 예외를 던진다")
    void startSession_duplicateActive() {
        Route route = mockRoute("route-1");
        when(routeRepository.findById("route-1")).thenReturn(Optional.of(route));
        when(runSessionRepository.existsByUser_IdAndRoute_IdAndStatus("user-1", "route-1", SessionStatus.ACTIVE)).thenReturn(true);

        assertThatThrownBy(() -> sessionService.startSession("user-1", new StartSessionRequest("route-1")))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("ACTIVE 세션을 PAUSED로 전환한다")
    void pauseSession_success() {
        User user = mockUser();
        Route route = mockRoute("route-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user).route(route).status(SessionStatus.ACTIVE).build();

        when(runSessionRepository.findByIdAndUser_Id("session-1", "user-1")).thenReturn(Optional.of(session));
        when(runSessionRepository.save(any())).thenReturn(session);

        sessionService.pauseSession("user-1", "session-1");

        assertThat(session.getStatus()).isEqualTo(SessionStatus.PAUSED);
        verify(runSessionRepository).save(session);
    }

    @Test
    @DisplayName("PAUSED 세션을 ACTIVE로 재개한다")
    void resumeSession_success() {
        User user = mockUser();
        Route route = mockRoute("route-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user).route(route).status(SessionStatus.PAUSED).build();

        when(runSessionRepository.findByIdAndUser_Id("session-1", "user-1")).thenReturn(Optional.of(session));
        when(runSessionRepository.save(any())).thenReturn(session);

        sessionService.resumeSession("user-1", "session-1");

        assertThat(session.getStatus()).isEqualTo(SessionStatus.ACTIVE);
    }

    @Test
    @DisplayName("ACTIVE 세션을 FINISHED로 종료한다")
    void finishSession_success() {
        User user = mockUser();
        Route route = mockRoute("route-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user).route(route).status(SessionStatus.ACTIVE).build();

        when(runSessionRepository.findByIdAndUser_Id("session-1", "user-1")).thenReturn(Optional.of(session));
        when(runSessionRepository.save(any())).thenReturn(session);

        SessionResponse response = sessionService.finishSession("user-1", "session-1");

        assertThat(session.getStatus()).isEqualTo(SessionStatus.FINISHED);
        assertThat(response.getStatus()).isEqualTo("FINISHED");
    }

    @Test
    @DisplayName("이미 완료된 세션은 종료할 수 없다")
    void finishSession_alreadyCompleted() {
        User user = mockUser();
        Route route = mockRoute("route-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user).route(route).status(SessionStatus.COMPLETED).build();

        when(runSessionRepository.findByIdAndUser_Id("session-1", "user-1")).thenReturn(Optional.of(session));

        assertThatThrownBy(() -> sessionService.finishSession("user-1", "session-1"))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("진행 중인 세션을 취소한다")
    void cancelSession_success() {
        User user = mockUser();
        Route route = mockRoute("route-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user).route(route).status(SessionStatus.ACTIVE).build();

        when(runSessionRepository.findByIdAndUser_Id("session-1", "user-1")).thenReturn(Optional.of(session));
        when(runSessionRepository.save(any())).thenReturn(session);

        sessionService.cancelSession("user-1", "session-1");

        assertThat(session.getStatus()).isEqualTo(SessionStatus.CANCELLED);
    }

    @Test
    @DisplayName("세션 상태를 조회한다")
    void getSession_success() {
        User user = mockUser();
        Route route = mockRoute("route-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user).route(route).status(SessionStatus.ACTIVE).build();

        when(runSessionRepository.findByIdAndUser_Id("session-1", "user-1")).thenReturn(Optional.of(session));

        SessionDetailResponse response = sessionService.getSession("user-1", "session-1");

        assertThat(response.getSessionId()).isEqualTo("session-1");
        assertThat(response.getStatus()).isEqualTo("ACTIVE");
    }

    @Test
    @DisplayName("다른 유저의 세션은 조회할 수 없다")
    void getSession_otherUser_notFound() {
        when(runSessionRepository.findByIdAndUser_Id("session-1", "other-user")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> sessionService.getSession("other-user", "session-1"))
                .isInstanceOf(BusinessException.class);
    }
}
