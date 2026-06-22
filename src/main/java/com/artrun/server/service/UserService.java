package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.User;
import com.artrun.server.dto.request.UpdateUserRequest;
import com.artrun.server.dto.response.*;
import com.artrun.server.repository.CommunityRouteRepository;
import com.artrun.server.repository.RouteLikeRepository;
import com.artrun.server.repository.RunRecordRepository;
import com.artrun.server.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.Arrays;
import java.util.List;

@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final RunRecordRepository runRecordRepository;
    private final CommunityRouteRepository communityRouteRepository;
    private final RouteLikeRepository routeLikeRepository;

    @Transactional(readOnly = true)
    public UserResponse getMe(String userId) {
        User user = findUser(userId);
        return UserResponse.from(user);
    }

    @Transactional
    public UserResponse updateMe(String userId, UpdateUserRequest request) {
        User user = findUser(userId);

        if (StringUtils.hasText(request.getNickname())) {
            if (userRepository.existsByNickname(request.getNickname())) {
                throw new BusinessException(ErrorCode.NICKNAME_ALREADY_EXISTS);
            }
            user.setNickname(request.getNickname());
        }
        if (request.getProfileImageUrl() != null) {
            user.setProfileImageUrl(request.getProfileImageUrl());
        }

        return UserResponse.from(userRepository.save(user));
    }

    @Transactional(readOnly = true)
    public MyPageSummaryResponse getSummary(String userId) {
        User user = findUser(userId);
        long totalRuns = runRecordRepository.countByUser_Id(userId);
        double totalDistanceM = runRecordRepository.sumDistanceByUserId(userId);
        long totalTimeSeconds = runRecordRepository.sumTimeByUserId(userId);

        double totalDistanceKm = totalDistanceM / 1000.0;
        double avgPace = (totalDistanceKm > 0)
                ? (totalTimeSeconds / 60.0) / totalDistanceKm
                : 0.0;

        return MyPageSummaryResponse.builder()
                .user(UserResponse.from(user))
                .totalRuns(totalRuns)
                .totalDistanceKm(totalDistanceKm)
                .totalTimeSeconds(totalTimeSeconds)
                .averagePaceMinPerKm(avgPace)
                .build();
    }

    @Transactional(readOnly = true)
    public Page<RecordDetailResponse> getMyRecords(String userId, Pageable pageable) {
        return runRecordRepository.findByUser_IdOrderByCreatedAtDesc(userId, pageable)
                .map(record -> {
                    List<RecordDetailResponse.LatLng> actual = record.getCorrectedPolyline() != null
                            ? Arrays.stream(record.getCorrectedPolyline().getCoordinates())
                                .map(c -> RecordDetailResponse.LatLng.builder().lat(c.y).lng(c.x).build())
                                .toList()
                            : List.of();

                    return RecordDetailResponse.builder()
                            .recordId(record.getId())
                            .routeId(record.getSession().getRoute().getId())
                            .actualPolyline(actual)
                            .totalDistanceMeters(record.getTotalDistanceMeters())
                            .totalTimeSeconds(record.getTotalTimeSeconds())
                            .averageSpeed(record.getAverageSpeed())
                            .imageUrl(record.getImageUrl())
                            .createdAt(record.getCreatedAt())
                            .build();
                });
    }

    @Transactional(readOnly = true)
    public RecordDetailResponse getMyRecord(String userId, String recordId) {
        var record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        List<RecordDetailResponse.LatLng> planned = record.getSession().getRoute().getPolyline() != null
                ? Arrays.stream(record.getSession().getRoute().getPolyline().getCoordinates())
                    .map(c -> RecordDetailResponse.LatLng.builder().lat(c.y).lng(c.x).build())
                    .toList()
                : List.of();

        List<RecordDetailResponse.LatLng> actual = record.getCorrectedPolyline() != null
                ? Arrays.stream(record.getCorrectedPolyline().getCoordinates())
                    .map(c -> RecordDetailResponse.LatLng.builder().lat(c.y).lng(c.x).build())
                    .toList()
                : List.of();

        return RecordDetailResponse.builder()
                .recordId(record.getId())
                .routeId(record.getSession().getRoute().getId())
                .plannedPolyline(planned)
                .actualPolyline(actual)
                .totalDistanceMeters(record.getTotalDistanceMeters())
                .totalTimeSeconds(record.getTotalTimeSeconds())
                .averageSpeed(record.getAverageSpeed())
                .imageUrl(record.getImageUrl())
                .createdAt(record.getCreatedAt())
                .build();
    }

    @Transactional(readOnly = true)
    public Page<CommunityRouteResponse> getLikedRoutes(String userId, Pageable pageable) {
        return routeLikeRepository.findByUser_IdOrderByCreatedAtDesc(userId, pageable)
                .map(like -> {
                    var cr = like.getCommunityRoute();
                    return CommunityRouteResponse.builder()
                            .communityRouteId(cr.getId())
                            .title(cr.getTitle())
                            .description(cr.getDescription())
                            .author(UserResponse.from(cr.getUser()))
                            .distanceMeters(cr.getRecord().getTotalDistanceMeters())
                            .likeCount(cr.getLikeCount())
                            .liked(true)
                            .createdAt(cr.getCreatedAt())
                            .build();
                });
    }

    @Transactional(readOnly = true)
    public Page<CommunityRouteResponse> getMySharedRoutes(String userId, Pageable pageable) {
        return communityRouteRepository.findByUser_IdOrderByCreatedAtDesc(userId, pageable)
                .map(cr -> CommunityRouteResponse.builder()
                        .communityRouteId(cr.getId())
                        .title(cr.getTitle())
                        .description(cr.getDescription())
                        .distanceMeters(cr.getRecord().getTotalDistanceMeters())
                        .likeCount(cr.getLikeCount())
                        .createdAt(cr.getCreatedAt())
                        .build());
    }

    @Transactional
    public void deleteMyRecord(String userId, String recordId) {
        var record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        if (communityRouteRepository.existsByRecord_Id(recordId)) {
            throw new BusinessException(ErrorCode.RECORD_IN_COMMUNITY);
        }

        runRecordRepository.delete(record);
    }

    private User findUser(String userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));
    }
}
