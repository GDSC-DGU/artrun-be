package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.User;
import com.artrun.server.dto.request.SaveRecordRequest;
import com.artrun.server.dto.request.UpdateUserRequest;
import com.artrun.server.dto.response.*;
import com.artrun.server.repository.CommunityRouteRepository;
import com.artrun.server.repository.RouteLikeRepository;
import com.artrun.server.repository.RunRecordRepository;
import com.artrun.server.repository.UserRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserService {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

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
    public UpdateUserResponse updateMe(String userId, UpdateUserRequest request) {
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

        User saved = userRepository.save(user);
        return UpdateUserResponse.builder()
                .userId(saved.getId())
                .nickname(saved.getNickname())
                .profileImageUrl(saved.getProfileImageUrl())
                .updatedAt(saved.getUpdatedAt())
                .build();
    }

    @Transactional(readOnly = true)
    public MyPageSummaryResponse getSummary(String userId) {
        User user = findUser(userId);
        long totalRunCount = runRecordRepository.countByUser_Id(userId);
        double totalDistanceM = runRecordRepository.sumDistanceByUserId(userId);
        long sharedRouteCount = communityRouteRepository.countByUser_Id(userId);
        long likedRouteCount = routeLikeRepository.countByUser_Id(userId);

        double totalDistanceKm = Math.round(totalDistanceM / 10.0) / 100.0;

        return MyPageSummaryResponse.builder()
                .userId(user.getId())
                .nickname(user.getNickname())
                .profileImageUrl(user.getProfileImageUrl())
                .totalDistanceKm(totalDistanceKm)
                .totalRunCount(totalRunCount)
                .sharedRouteCount(sharedRouteCount)
                .likedRouteCount(likedRouteCount)
                .build();
    }

    @Transactional(readOnly = true)
    public RecordListResponse getMyRecords(String userId, Pageable pageable) {
        var page = runRecordRepository.findByUser_IdOrderByCreatedAtDesc(userId, pageable);
        java.util.Set<String> sharedIds = communityRouteRepository.findSharedRecordIdsByUserId(userId);

        List<RecordSummaryResponse> records = page.getContent().stream()
                .map(record -> {
                    var route = record.getSession().getRoute();
                    var task = route != null ? route.getTask() : null;
                    double distanceKm = record.getTotalDistanceMeters() != null
                            ? Math.round(record.getTotalDistanceMeters() / 10.0) / 100.0 : 0;
                    int pace = record.getAveragePaceSecPerKm() != null ? record.getAveragePaceSecPerKm() : 0;

                    return RecordSummaryResponse.builder()
                            .recordId(record.getId())
                            .routeId(route != null ? route.getId() : null)
                            .routeName(route != null ? route.getRouteName() : null)
                            .shapeType(task != null ? task.getShapeType() : null)
                            .distanceKm(distanceKm)
                            .averagePace(formatPaceText(pace))
                            .totalTimeSeconds(record.getTotalTimeSeconds() != null ? record.getTotalTimeSeconds() : 0)
                            .matchRate(record.getMatchRate() != null ? record.getMatchRate() : 0)
                            .imageUrl(record.getImageUrl())
                            .shared(sharedIds.contains(record.getId()))
                            .completedAt(record.getCreatedAt())
                            .build();
                })
                .toList();

        return RecordListResponse.builder()
                .totalCount(page.getTotalElements())
                .records(records)
                .build();
    }

    @Transactional(readOnly = true)
    public MyRecordDetailResponse getMyRecord(String userId, String recordId) {
        var record = runRecordRepository.findByIdAndUser_Id(recordId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        var route = record.getSession().getRoute();
        var task = route != null ? route.getTask() : null;
        double distanceKm = record.getTotalDistanceMeters() != null
                ? Math.round(record.getTotalDistanceMeters() / 10.0) / 100.0 : 0;
        int pace = record.getAveragePaceSecPerKm() != null ? record.getAveragePaceSecPerKm() : 0;

        List<MyRecordDetailResponse.LatLng> routePolyline = List.of();
        if (route != null && route.getPolyline() != null) {
            var coords = route.getPolyline().getCoordinates();
            routePolyline = java.util.Arrays.stream(coords)
                    .map(c -> MyRecordDetailResponse.LatLng.builder().lat(c.y).lng(c.x).build())
                    .toList();
        }

        List<MyRecordDetailResponse.GpsPoint> actualGpsPoints = parseActualGps(record.getRawGpsJson());
        boolean shared = communityRouteRepository.existsByRecord_Id(recordId);

        return MyRecordDetailResponse.builder()
                .recordId(record.getId())
                .routeId(route != null ? route.getId() : null)
                .routeName(route != null ? route.getRouteName() : null)
                .shapeType(task != null ? task.getShapeType() : null)
                .distanceKm(distanceKm)
                .averagePace(formatPaceText(pace))
                .averageBpm(record.getAverageBpm() != null ? record.getAverageBpm() : 0)
                .totalTimeSeconds(record.getTotalTimeSeconds() != null ? record.getTotalTimeSeconds() : 0)
                .matchRate(record.getMatchRate() != null ? record.getMatchRate() : 0)
                .imageUrl(record.getImageUrl())
                .shared(shared)
                .routePolyline(routePolyline)
                .actualGpsPoints(actualGpsPoints)
                .completedAt(record.getCreatedAt())
                .build();
    }

    private List<MyRecordDetailResponse.GpsPoint> parseActualGps(String rawGpsJson) {
        if (rawGpsJson == null) return List.of();
        try {
            List<SaveRecordRequest.GpsPoint> points = OBJECT_MAPPER.readValue(
                    rawGpsJson, new TypeReference<>() {});
            return points.stream()
                    .map(p -> MyRecordDetailResponse.GpsPoint.builder()
                            .lat(p.getLat()).lng(p.getLng()).timestamp(p.getTimestamp()).build())
                    .toList();
        } catch (Exception e) {
            log.warn("Failed to parse rawGpsJson: {}", e.getMessage());
            return List.of();
        }
    }

    private List<RecordDetailResponse.CorrectedPolylinePoint> buildCorrectedPoints(
            com.artrun.server.domain.RunRecord record) {
        if (record.getCorrectedPolyline() == null) return List.of();
        var coords = record.getCorrectedPolyline().getCoordinates();
        return java.util.stream.IntStream.range(0, coords.length)
                .mapToObj(i -> RecordDetailResponse.CorrectedPolylinePoint.builder()
                        .lat(coords[i].y).lng(coords[i].x).order(i + 1).build())
                .toList();
    }

    private String formatPaceText(int paceSecPerKm) {
        if (paceSecPerKm <= 0) return "0'00\"";
        return String.format("%d'%02d\"", paceSecPerKm / 60, paceSecPerKm % 60);
    }

    @Transactional(readOnly = true)
    public LikedRouteListResponse getLikedRoutes(String userId, Pageable pageable) {
        var page = routeLikeRepository.findByUser_IdOrderByCreatedAtDesc(userId, pageable);
        List<LikedRouteResponse> routes = page.getContent().stream()
                .map(like -> {
                    var cr = like.getCommunityRoute();
                    var record = cr.getRecord();
                    var route = record != null ? record.getSession().getRoute() : null;
                    var task = route != null ? route.getTask() : null;
                    int pace = record != null && record.getAveragePaceSecPerKm() != null
                            ? record.getAveragePaceSecPerKm() : 0;
                    return LikedRouteResponse.builder()
                            .routeId(route != null ? route.getId() : null)
                            .title(cr.getTitle())
                            .shapeType(task != null ? task.getShapeType() : null)
                            .distanceKm(toDistanceKm(record))
                            .averagePace(formatPaceText(pace))
                            .locationName(cr.getLocationName())
                            .creatorNickname(cr.getUser() != null ? cr.getUser().getNickname() : null)
                            .thumbnailUrl(record != null ? record.getImageUrl() : null)
                            .likeCount(cr.getLikeCount())
                            .likedAt(like.getCreatedAt())
                            .build();
                })
                .toList();
        return LikedRouteListResponse.builder()
                .totalCount(page.getTotalElements())
                .routes(routes)
                .build();
    }

    @Transactional(readOnly = true)
    public SharedRouteListResponse getMySharedRoutes(String userId, Pageable pageable) {
        var page = communityRouteRepository.findByUser_IdOrderByCreatedAtDesc(userId, pageable);
        List<SharedRouteResponse> routes = page.getContent().stream()
                .map(cr -> {
                    var record = cr.getRecord();
                    var route = record != null ? record.getSession().getRoute() : null;
                    return SharedRouteResponse.builder()
                            .communityRouteId(cr.getId())
                            .recordId(record != null ? record.getId() : null)
                            .routeId(route != null ? route.getId() : null)
                            .title(cr.getTitle())
                            .description(cr.getDescription())
                            .distanceKm(toDistanceKm(record))
                            .imageUrl(record != null ? record.getImageUrl() : null)
                            .likeCount(cr.getLikeCount())
                            .createdAt(cr.getCreatedAt())
                            .build();
                })
                .toList();
        return SharedRouteListResponse.builder()
                .totalCount(page.getTotalElements())
                .routes(routes)
                .build();
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

    private CommunityRouteResponse.CreatorDto toCommunityCreatorDto(com.artrun.server.domain.User user) {
        if (user == null) return null;
        return CommunityRouteResponse.CreatorDto.builder()
                .userId(user.getId())
                .nickname(user.getNickname())
                .profileImageUrl(user.getProfileImageUrl())
                .build();
    }

    private double toDistanceKm(com.artrun.server.domain.RunRecord record) {
        if (record == null || record.getTotalDistanceMeters() == null) return 0;
        return Math.round(record.getTotalDistanceMeters() / 10.0) / 100.0;
    }

    private User findUser(String userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));
    }
}
