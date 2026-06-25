package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.AuthProvider;
import com.artrun.server.domain.User;
import com.artrun.server.dto.response.MyPageSummaryResponse;
import com.artrun.server.dto.response.UserResponse;
import com.artrun.server.repository.CommunityRouteRepository;
import com.artrun.server.repository.RouteLikeRepository;
import com.artrun.server.repository.RunRecordRepository;
import com.artrun.server.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock UserRepository userRepository;
    @Mock RunRecordRepository runRecordRepository;
    @Mock CommunityRouteRepository communityRouteRepository;
    @Mock RouteLikeRepository routeLikeRepository;

    @InjectMocks UserService userService;

    private User mockUser(String id) {
        return User.builder().id(id).email("test@test.com")
                .nickname("테스터").provider(AuthProvider.EMAIL).build();
    }

    @Test
    @DisplayName("내 정보를 조회한다")
    void getMe_success() {
        User user = mockUser("user-1");
        when(userRepository.findById("user-1")).thenReturn(Optional.of(user));

        UserResponse response = userService.getMe("user-1");

        assertThat(response.getUserId()).isEqualTo("user-1");
        assertThat(response.getNickname()).isEqualTo("테스터");
    }

    @Test
    @DisplayName("존재하지 않는 유저는 예외를 던진다")
    void getMe_userNotFound() {
        when(userRepository.findById("no-user")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.getMe("no-user"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.USER_NOT_FOUND);
    }

    @Test
    @DisplayName("마이페이지 요약 통계를 계산한다")
    void getSummary_calculatesCorrectly() {
        User user = mockUser("user-1");
        when(userRepository.findById("user-1")).thenReturn(Optional.of(user));
        when(runRecordRepository.countByUser_Id("user-1")).thenReturn(5L);
        when(runRecordRepository.sumDistanceByUserId("user-1")).thenReturn(25000.0); // 25km
        when(communityRouteRepository.countByUser_Id("user-1")).thenReturn(2L);
        when(routeLikeRepository.countByUser_Id("user-1")).thenReturn(7L);

        MyPageSummaryResponse summary = userService.getSummary("user-1");

        assertThat(summary.getTotalRunCount()).isEqualTo(5);
        assertThat(summary.getTotalDistanceKm()).isEqualTo(25.0);
        assertThat(summary.getSharedRouteCount()).isEqualTo(2);
        assertThat(summary.getLikedRouteCount()).isEqualTo(7);
    }

    @Test
    @DisplayName("커뮤니티에 등록된 기록은 삭제할 수 없다")
    void deleteMyRecord_inCommunity_throws() {
        User user = mockUser("user-1");
        var record = com.artrun.server.domain.RunRecord.builder()
                .id("record-1").user(user).build();

        when(runRecordRepository.findByIdAndUser_Id("record-1", "user-1")).thenReturn(Optional.of(record));
        when(communityRouteRepository.existsByRecord_Id("record-1")).thenReturn(true);

        assertThatThrownBy(() -> userService.deleteMyRecord("user-1", "record-1"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.RECORD_IN_COMMUNITY);
    }

    @Test
    @DisplayName("커뮤니티에 없는 기록을 삭제한다")
    void deleteMyRecord_success() {
        User user = mockUser("user-1");
        var record = com.artrun.server.domain.RunRecord.builder()
                .id("record-1").user(user).build();

        when(runRecordRepository.findByIdAndUser_Id("record-1", "user-1")).thenReturn(Optional.of(record));
        when(communityRouteRepository.existsByRecord_Id("record-1")).thenReturn(false);

        userService.deleteMyRecord("user-1", "record-1");

        verify(runRecordRepository).delete(record);
    }
}
