package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.*;
import com.artrun.server.dto.request.PrepareRunRequest;
import com.artrun.server.dto.request.RegisterCommunityRouteRequest;
import com.artrun.server.dto.response.PrepareRunResponse;
import com.artrun.server.repository.*;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.locationtech.jts.geom.*;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class CommunityServiceTest {

    @Mock CommunityRouteRepository communityRouteRepository;
    @Mock RouteLikeRepository routeLikeRepository;
    @Mock RunRecordRepository runRecordRepository;
    @Mock UserRepository userRepository;
    @Mock JdbcTemplate jdbcTemplate;

    @InjectMocks CommunityService communityService;

    private User mockUser(String id) {
        return User.builder().id(id).email("test@test.com")
                .nickname("테스터").provider(AuthProvider.EMAIL).build();
    }

    @Test
    @DisplayName("이미 등록된 기록은 커뮤니티에 중복 등록할 수 없다")
    void register_duplicate_throws() {
        when(communityRouteRepository.existsByRecord_Id("record-1")).thenReturn(true);

        RegisterCommunityRouteRequest req = makeRegisterReq("record-1", "제목", null);

        assertThatThrownBy(() -> communityService.register("user-1", req))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMMUNITY_ROUTE_ALREADY_EXISTS);
    }

    @Test
    @DisplayName("완주하지 않은 기록은 커뮤니티에 등록할 수 없다")
    void register_notCompleted_throws() {
        User user = mockUser("user-1");
        RunSession session = RunSession.builder()
                .id("session-1").user(user)
                .route(Route.builder().id("route-1").build())
                .status(SessionStatus.FINISHED).build(); // COMPLETED 아님
        RunRecord record = RunRecord.builder()
                .id("record-1").user(user).session(session).build();

        when(communityRouteRepository.existsByRecord_Id("record-1")).thenReturn(false);
        when(runRecordRepository.findByIdAndUser_Id("record-1", "user-1")).thenReturn(Optional.of(record));

        RegisterCommunityRouteRequest req = makeRegisterReq("record-1", "제목", null);

        assertThatThrownBy(() -> communityService.register("user-1", req))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.NOT_COMPLETED_RECORD);
    }

    @Test
    @DisplayName("본인 글이 아닌 커뮤니티 루트는 삭제할 수 없다")
    void delete_otherUser_throws() {
        User owner = mockUser("owner-id");
        CommunityRoute cr = CommunityRoute.builder().id("cr-1").user(owner).build();
        when(communityRouteRepository.findById("cr-1")).thenReturn(Optional.of(cr));

        assertThatThrownBy(() -> communityService.delete("other-user", "cr-1"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COMMUNITY_ROUTE_FORBIDDEN);
    }

    @Test
    @DisplayName("이미 좋아요한 루트에 다시 좋아요하면 예외를 던진다")
    void like_duplicate_throws() {
        when(routeLikeRepository.existsByUser_IdAndCommunityRoute_Id("user-1", "cr-1")).thenReturn(true);

        assertThatThrownBy(() -> communityService.like("user-1", "cr-1"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.LIKE_ALREADY_EXISTS);
    }

    @Test
    @DisplayName("좋아요하지 않은 루트를 취소하면 예외를 던진다")
    void unlike_notFound_throws() {
        when(routeLikeRepository.findByUser_IdAndCommunityRoute_Id("user-1", "cr-1"))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> communityService.unlike("user-1", "cr-1"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.LIKE_NOT_FOUND);
    }

    @Test
    @DisplayName("출발점 300m 이내면 canRun=true를 반환한다")
    void prepareRun_withinThreshold_canRun() {
        GeometryFactory gf = new GeometryFactory(new PrecisionModel(), 4326);
        // 서울시청 근처 두 점 (약 100m 간격)
        LineString line = gf.createLineString(new Coordinate[]{
                new Coordinate(126.9780, 37.5665),
                new Coordinate(126.9790, 37.5675)
        });

        Route route = Route.builder().id("route-1").polyline(line).build();
        RunSession session = RunSession.builder().id("s-1").route(route)
                .status(SessionStatus.COMPLETED).build();
        RunRecord record = RunRecord.builder().id("rec-1").session(session).build();
        CommunityRoute cr = CommunityRoute.builder().id("cr-1").record(record).build();

        when(communityRouteRepository.findById("cr-1")).thenReturn(Optional.of(cr));

        PrepareRunRequest req = new PrepareRunRequest();
        PrepareRunRequest.CurrentPointDto cp1 = new PrepareRunRequest.CurrentPointDto();
        setField(cp1, "lat", 37.5666); // 출발점에서 약 11m
        setField(cp1, "lng", 126.9781);
        setField(req, "currentPoint", cp1);

        PrepareRunResponse response = communityService.prepareRun("cr-1", req);

        assertThat(response.isRunnable()).isTrue();
        assertThat(response.getRouteId()).isEqualTo("route-1");
    }

    @Test
    @DisplayName("출발점 300m 초과면 canRun=false를 반환한다")
    void prepareRun_outsideThreshold_cannotRun() {
        GeometryFactory gf = new GeometryFactory(new PrecisionModel(), 4326);
        LineString line = gf.createLineString(new Coordinate[]{
                new Coordinate(126.9780, 37.5665),
                new Coordinate(126.9790, 37.5675)
        });

        Route route = Route.builder().id("route-1").polyline(line).build();
        RunSession session = RunSession.builder().id("s-1").route(route)
                .status(SessionStatus.COMPLETED).build();
        RunRecord record = RunRecord.builder().id("rec-1").session(session).build();
        CommunityRoute cr = CommunityRoute.builder().id("cr-1").record(record).build();

        when(communityRouteRepository.findById("cr-1")).thenReturn(Optional.of(cr));

        PrepareRunRequest req = new PrepareRunRequest();
        PrepareRunRequest.CurrentPointDto cp2 = new PrepareRunRequest.CurrentPointDto();
        setField(cp2, "lat", 37.600); // 출발점에서 약 4km 이상
        setField(cp2, "lng", 127.000);
        setField(req, "currentPoint", cp2);

        PrepareRunResponse response = communityService.prepareRun("cr-1", req);

        assertThat(response.isRunnable()).isFalse();
    }

    private RegisterCommunityRouteRequest makeRegisterReq(String recordId, String title, String desc) {
        RegisterCommunityRouteRequest req = new RegisterCommunityRouteRequest();
        setField(req, "recordId", recordId);
        setField(req, "title", title);
        setField(req, "description", desc);
        return req;
    }

    private void setField(Object obj, String name, Object value) {
        try {
            var field = obj.getClass().getDeclaredField(name);
            field.setAccessible(true);
            field.set(obj, value);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
