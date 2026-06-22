package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.*;
import com.artrun.server.dto.request.PrepareRunRequest;
import com.artrun.server.dto.request.RegisterCommunityRouteRequest;
import com.artrun.server.dto.response.CommunityRouteResponse;
import com.artrun.server.dto.response.PrepareRunResponse;
import com.artrun.server.dto.response.UserResponse;
import com.artrun.server.repository.*;
import lombok.RequiredArgsConstructor;
import org.locationtech.jts.geom.Coordinate;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;

@Service
@RequiredArgsConstructor
public class CommunityService {

    private static final double START_POINT_THRESHOLD_M = 300.0;

    private final CommunityRouteRepository communityRouteRepository;
    private final RouteLikeRepository routeLikeRepository;
    private final RunRecordRepository runRecordRepository;
    private final UserRepository userRepository;

    @Transactional(readOnly = true)
    public Page<CommunityRouteResponse> getRoutes(String userId, Pageable pageable) {
        return communityRouteRepository.findAllByOrderByCreatedAtDesc(pageable)
                .map(cr -> toResponse(cr, userId));
    }

    @Transactional(readOnly = true)
    public CommunityRouteResponse getRoute(String communityRouteId, String userId) {
        CommunityRoute cr = findCommunityRoute(communityRouteId);
        return toDetailResponse(cr, userId);
    }

    @Transactional
    public CommunityRouteResponse register(String userId, RegisterCommunityRouteRequest request) {
        if (communityRouteRepository.existsByRecord_Id(request.getRecordId())) {
            throw new BusinessException(ErrorCode.COMMUNITY_ROUTE_ALREADY_EXISTS);
        }

        RunRecord record = runRecordRepository.findByIdAndUser_Id(request.getRecordId(), userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RECORD_NOT_FOUND));

        if (record.getSession().getStatus() != SessionStatus.COMPLETED) {
            throw new BusinessException(ErrorCode.NOT_COMPLETED_RECORD);
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        CommunityRoute cr = CommunityRoute.builder()
                .record(record)
                .user(user)
                .title(request.getTitle())
                .description(request.getDescription())
                .build();

        return toDetailResponse(communityRouteRepository.save(cr), userId);
    }

    @Transactional
    public void delete(String userId, String communityRouteId) {
        CommunityRoute cr = findCommunityRoute(communityRouteId);
        if (!cr.getUser().getId().equals(userId)) {
            throw new BusinessException(ErrorCode.COMMUNITY_ROUTE_FORBIDDEN);
        }
        communityRouteRepository.delete(cr);
    }

    @Transactional
    public void like(String userId, String communityRouteId) {
        if (routeLikeRepository.existsByUser_IdAndCommunityRoute_Id(userId, communityRouteId)) {
            throw new BusinessException(ErrorCode.LIKE_ALREADY_EXISTS);
        }
        CommunityRoute cr = findCommunityRoute(communityRouteId);
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        routeLikeRepository.save(RouteLike.builder().user(user).communityRoute(cr).build());
        communityRouteRepository.incrementLikeCount(communityRouteId);
    }

    @Transactional
    public void unlike(String userId, String communityRouteId) {
        RouteLike like = routeLikeRepository.findByUser_IdAndCommunityRoute_Id(userId, communityRouteId)
                .orElseThrow(() -> new BusinessException(ErrorCode.LIKE_NOT_FOUND));
        routeLikeRepository.delete(like);
        communityRouteRepository.decrementLikeCount(communityRouteId);
    }

    @Transactional(readOnly = true)
    public PrepareRunResponse prepareRun(String communityRouteId, PrepareRunRequest request) {
        CommunityRoute cr = findCommunityRoute(communityRouteId);
        var polyline = cr.getRecord().getSession().getRoute().getPolyline();

        double distanceToStart = Double.MAX_VALUE;
        if (polyline != null && polyline.getNumPoints() > 0) {
            Coordinate start = polyline.getCoordinateN(0);
            distanceToStart = haversineMeters(request.getLat(), request.getLng(), start.y, start.x);
        }

        boolean canRun = distanceToStart <= START_POINT_THRESHOLD_M;
        return PrepareRunResponse.builder()
                .routeId(cr.getRecord().getSession().getRoute().getId())
                .distanceToStart(distanceToStart)
                .canRun(canRun)
                .build();
    }

    private CommunityRoute findCommunityRoute(String id) {
        return communityRouteRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMMUNITY_ROUTE_NOT_FOUND));
    }

    private CommunityRouteResponse toResponse(CommunityRoute cr, String userId) {
        boolean liked = userId != null &&
                routeLikeRepository.existsByUser_IdAndCommunityRoute_Id(userId, cr.getId());
        return CommunityRouteResponse.builder()
                .communityRouteId(cr.getId())
                .title(cr.getTitle())
                .author(UserResponse.from(cr.getUser()))
                .distanceMeters(cr.getRecord().getTotalDistanceMeters())
                .likeCount(cr.getLikeCount())
                .liked(liked)
                .createdAt(cr.getCreatedAt())
                .build();
    }

    private CommunityRouteResponse toDetailResponse(CommunityRoute cr, String userId) {
        boolean liked = userId != null &&
                routeLikeRepository.existsByUser_IdAndCommunityRoute_Id(userId, cr.getId());

        List<CommunityRouteResponse.LatLng> polyline = List.of();
        var line = cr.getRecord().getSession().getRoute().getPolyline();
        if (line != null) {
            polyline = Arrays.stream(line.getCoordinates())
                    .map(c -> CommunityRouteResponse.LatLng.builder().lat(c.y).lng(c.x).build())
                    .toList();
        }

        return CommunityRouteResponse.builder()
                .communityRouteId(cr.getId())
                .title(cr.getTitle())
                .description(cr.getDescription())
                .author(UserResponse.from(cr.getUser()))
                .routeId(cr.getRecord().getSession().getRoute().getId())
                .polyline(polyline)
                .distanceMeters(cr.getRecord().getTotalDistanceMeters())
                .totalTimeSeconds(cr.getRecord().getTotalTimeSeconds())
                .imageUrl(cr.getRecord().getImageUrl())
                .likeCount(cr.getLikeCount())
                .liked(liked)
                .createdAt(cr.getCreatedAt())
                .build();
    }

    private double haversineMeters(double lat1, double lng1, double lat2, double lng2) {
        final double R = 6371000;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }
}
