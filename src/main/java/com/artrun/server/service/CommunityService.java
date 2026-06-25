package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.domain.*;
import com.artrun.server.dto.request.PrepareRunRequest;
import com.artrun.server.dto.request.RegisterCommunityRouteRequest;
import com.artrun.server.dto.response.CommunityRouteListResponse;
import com.artrun.server.dto.response.CommunityRouteResponse;
import com.artrun.server.dto.response.LikeRouteResponse;
import com.artrun.server.dto.response.PrepareRunResponse;
import com.artrun.server.dto.response.RegisterCommunityRouteResponse;
import com.artrun.server.repository.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.LineString;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class CommunityService {

    private static final double START_POINT_THRESHOLD_M = 300.0;
    private static final double DEFAULT_RADIUS_KM = 5.0;

    private final CommunityRouteRepository communityRouteRepository;
    private final RouteLikeRepository routeLikeRepository;
    private final RunRecordRepository runRecordRepository;
    private final UserRepository userRepository;
    private final JdbcTemplate jdbcTemplate;

    @Transactional(readOnly = true)
    public CommunityRouteListResponse getRoutes(String userId, String keyword, String filter,
                                                String sort, Double lat, Double lng,
                                                Double radiusKm, int page, int size) {
        String kw = (keyword != null && !keyword.isBlank()) ? keyword.trim() : null;

        if ("NEARBY".equals(filter) || "DISTANCE_ASC".equals(sort)) {
            if (lat != null && lng != null) {
                return getNearbyRoutes(userId, kw, lat, lng,
                        radiusKm != null ? radiusKm : DEFAULT_RADIUS_KM, page, size);
            }
        }

        Pageable pageable = resolvePageable(filter, sort, page, size);

        Page<CommunityRoute> result;
        if ("MATCH_DESC".equals(sort)) {
            result = communityRouteRepository.searchOrderByMatchRateDesc(kw, PageRequest.of(page, size));
        } else {
            result = communityRouteRepository.searchByKeyword(kw, pageable);
        }

        return CommunityRouteListResponse.builder()
                .totalCount(result.getTotalElements())
                .routes(result.getContent().stream().map(cr -> toResponse(cr, userId)).toList())
                .build();
    }

    @Transactional(readOnly = true)
    public CommunityRouteResponse getRoute(String communityRouteId, String userId) {
        return toDetailResponse(findCommunityRoute(communityRouteId), userId);
    }

    @Transactional
    public RegisterCommunityRouteResponse register(String userId, RegisterCommunityRouteRequest request) {
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

        Route route = record.getSession().getRoute();
        String locationName = (route != null && route.getTask() != null)
                ? route.getTask().getStartAddressName() : null;
        String visibility = request.getVisibility() != null ? request.getVisibility() : "PUBLIC";

        CommunityRoute cr = CommunityRoute.builder()
                .record(record)
                .user(user)
                .title(request.getTitle())
                .description(request.getDescription())
                .locationName(locationName)
                .tags(request.getTags() != null ? request.getTags() : new java.util.ArrayList<>())
                .visibility(visibility)
                .build();

        CommunityRoute saved = communityRouteRepository.save(cr);

        return RegisterCommunityRouteResponse.builder()
                .communityRouteId(saved.getId())
                .recordId(record.getId())
                .routeId(route != null ? route.getId() : null)
                .title(saved.getTitle())
                .visibility(saved.getVisibility())
                .createdAt(saved.getCreatedAt())
                .build();
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
    public LikeRouteResponse like(String userId, String communityRouteId) {
        if (routeLikeRepository.existsByUser_IdAndCommunityRoute_Id(userId, communityRouteId)) {
            throw new BusinessException(ErrorCode.LIKE_ALREADY_EXISTS);
        }
        CommunityRoute cr = findCommunityRoute(communityRouteId);
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));

        routeLikeRepository.save(RouteLike.builder().user(user).communityRoute(cr).build());
        communityRouteRepository.incrementLikeCount(communityRouteId);

        return LikeRouteResponse.builder()
                .communityRouteId(communityRouteId)
                .liked(true)
                .likeCount(cr.getLikeCount() + 1)
                .build();
    }

    @Transactional
    public LikeRouteResponse unlike(String userId, String communityRouteId) {
        RouteLike like = routeLikeRepository.findByUser_IdAndCommunityRoute_Id(userId, communityRouteId)
                .orElseThrow(() -> new BusinessException(ErrorCode.LIKE_NOT_FOUND));
        CommunityRoute cr = like.getCommunityRoute();
        routeLikeRepository.delete(like);
        communityRouteRepository.decrementLikeCount(communityRouteId);

        return LikeRouteResponse.builder()
                .communityRouteId(communityRouteId)
                .liked(false)
                .likeCount(Math.max(0, cr.getLikeCount() - 1))
                .build();
    }

    @Transactional(readOnly = true)
    public PrepareRunResponse prepareRun(String communityRouteId, PrepareRunRequest request) {
        CommunityRoute cr = findCommunityRoute(communityRouteId);
        Route route = cr.getRecord().getSession().getRoute();
        var polyline = route != null ? route.getPolyline() : null;

        double distanceToStart = 0;
        if (polyline != null && polyline.getNumPoints() > 0) {
            Coordinate start = polyline.getCoordinateN(0);
            distanceToStart = haversineMeters(
                    request.getCurrentPoint().getLat(),
                    request.getCurrentPoint().getLng(),
                    start.y, start.x);
        }

        boolean runnable = distanceToStart <= START_POINT_THRESHOLD_M;
        String msg = runnable
                ? "이 루트를 바로 시작할 수 있습니다."
                : String.format("출발점에서 %.0fm 떨어져 있습니다.", distanceToStart);

        return PrepareRunResponse.builder()
                .communityRouteId(communityRouteId)
                .routeId(route != null ? route.getId() : null)
                .runnable(runnable)
                .startDistanceMeters(Math.round(distanceToStart * 10.0) / 10.0)
                .message(msg)
                .build();
    }

    // ──────────────────────────────────────────────────────────────────

    private CommunityRouteListResponse getNearbyRoutes(String userId, String keyword,
                                                        double lat, double lng,
                                                        double radiusKm, int page, int size) {
        String likePredicate = keyword != null
                ? "AND (LOWER(cr.title) LIKE LOWER('%" + keyword.replace("'", "''") + "%') " +
                  "OR LOWER(cr.location_name) LIKE LOWER('%" + keyword.replace("'", "''") + "%'))"
                : "";

        String countSql = """
                SELECT COUNT(cr.id) FROM community_routes cr
                JOIN run_records rr ON cr.record_id = rr.id
                JOIN run_sessions rs ON rr.session_id = rs.id
                JOIN routes r ON rs.route_id = r.id
                WHERE r.polyline IS NOT NULL
                AND ST_DWithin(
                    ST_StartPoint(r.polyline)::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography,
                    ?
                )
                """ + likePredicate;

        String dataSql = """
                SELECT cr.id FROM community_routes cr
                JOIN run_records rr ON cr.record_id = rr.id
                JOIN run_sessions rs ON rr.session_id = rs.id
                JOIN routes r ON rs.route_id = r.id
                WHERE r.polyline IS NOT NULL
                AND ST_DWithin(
                    ST_StartPoint(r.polyline)::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography,
                    ?
                )
                """ + likePredicate + """
                ORDER BY ST_Distance(
                    ST_StartPoint(r.polyline)::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography
                ) ASC
                LIMIT ? OFFSET ?
                """;

        double radiusMeters = radiusKm * 1000;
        try {
            Long total = jdbcTemplate.queryForObject(countSql, Long.class, lng, lat, radiusMeters);
            List<String> ids = jdbcTemplate.queryForList(dataSql, String.class,
                    lng, lat, radiusMeters, lng, lat, size, (long) page * size);

            List<CommunityRouteResponse> routes = ids.stream()
                    .map(id -> communityRouteRepository.findById(id).orElse(null))
                    .filter(cr -> cr != null)
                    .map(cr -> toResponse(cr, userId))
                    .toList();

            return CommunityRouteListResponse.builder()
                    .totalCount(total != null ? total : 0)
                    .routes(routes)
                    .build();
        } catch (Exception e) {
            log.warn("Nearby search failed, falling back to default: {}", e.getMessage());
            return getRoutes(userId, keyword, "ALL", "RECENT_DESC", null, null, null, page, size);
        }
    }

    private Pageable resolvePageable(String filter, String sort, int page, int size) {
        Sort s = switch (filter != null ? filter : "") {
            case "POPULAR" -> Sort.by("likeCount").descending();
            case "RECENT" -> Sort.by("createdAt").descending();
            default -> switch (sort != null ? sort : "") {
                case "LIKE_DESC" -> Sort.by("likeCount").descending();
                case "RECENT_DESC" -> Sort.by("createdAt").descending();
                default -> Sort.by("createdAt").descending();
            };
        };
        return PageRequest.of(page, size, s);
    }

    private CommunityRoute findCommunityRoute(String id) {
        return communityRouteRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMMUNITY_ROUTE_NOT_FOUND));
    }

    public CommunityRouteResponse toResponse(CommunityRoute cr, String userId) {
        boolean liked = userId != null &&
                routeLikeRepository.existsByUser_IdAndCommunityRoute_Id(userId, cr.getId());
        RunRecord record = cr.getRecord();
        Route route = record != null ? record.getSession().getRoute() : null;
        RouteTask task = route != null ? route.getTask() : null;

        double distanceKm = record != null && record.getTotalDistanceMeters() != null
                ? Math.round(record.getTotalDistanceMeters() / 10.0) / 100.0 : 0;
        int pace = record != null && record.getAveragePaceSecPerKm() != null
                ? record.getAveragePaceSecPerKm() : 0;

        return CommunityRouteResponse.builder()
                .communityRouteId(cr.getId())
                .routeId(route != null ? route.getId() : null)
                .recordId(record != null ? record.getId() : null)
                .title(cr.getTitle())
                .shapeType(task != null ? task.getShapeType() : null)
                .activityType(task != null ? task.getActivityType() : null)
                .distanceKm(distanceKm)
                .averagePaceText(formatPace(pace))
                .totalTimeSeconds(record != null ? record.getTotalTimeSeconds() : null)
                .matchRate(record != null ? record.getMatchRate() : null)
                .locationName(cr.getLocationName())
                .thumbnailUrl(record != null ? record.getImageUrl() : null)
                .likeCount(cr.getLikeCount())
                .liked(liked)
                .creator(toCreatorDto(cr.getUser()))
                .createdAt(cr.getCreatedAt())
                .build();
    }

    private CommunityRouteResponse toDetailResponse(CommunityRoute cr, String userId) {
        CommunityRouteResponse base = toResponse(cr, userId);
        RunRecord record = cr.getRecord();
        Route route = record != null ? record.getSession().getRoute() : null;
        int bpm = record != null && record.getAverageBpm() != null ? record.getAverageBpm() : 0;

        return CommunityRouteResponse.builder()
                .communityRouteId(base.getCommunityRouteId())
                .routeId(base.getRouteId())
                .recordId(base.getRecordId())
                .title(base.getTitle())
                .description(cr.getDescription())
                .shapeType(base.getShapeType())
                .activityType(base.getActivityType())
                .distanceKm(base.getDistanceKm())
                .averagePaceText(base.getAveragePaceText())
                .totalTimeSeconds(base.getTotalTimeSeconds())
                .averageBpm(bpm)
                .matchRate(base.getMatchRate())
                .locationName(base.getLocationName())
                .thumbnailUrl(base.getThumbnailUrl())
                .imageUrl(record != null ? record.getImageUrl() : null)
                .likeCount(base.getLikeCount())
                .liked(base.getLiked())
                .creator(base.getCreator())
                .route(buildRouteDetail(route))
                .createdAt(base.getCreatedAt())
                .build();
    }

    private CommunityRouteResponse.RouteDetailDto buildRouteDetail(Route route) {
        if (route == null) return null;
        LineString polyline = route.getPolyline();

        CommunityRouteResponse.LatLngDto startPoint = null;
        CommunityRouteResponse.LatLngDto endPoint = null;
        CommunityRouteResponse.BoundsDto bounds = null;
        List<CommunityRouteResponse.PolylinePointDto> polylinePoints = List.of();

        if (polyline != null && polyline.getNumPoints() > 0) {
            Coordinate[] coords = polyline.getCoordinates();
            Coordinate first = coords[0];
            Coordinate last = coords[coords.length - 1];

            startPoint = CommunityRouteResponse.LatLngDto.builder()
                    .lat(first.y).lng(first.x).build();
            endPoint = CommunityRouteResponse.LatLngDto.builder()
                    .lat(last.y).lng(last.x).build();

            double minLat = Double.MAX_VALUE, maxLat = -Double.MAX_VALUE;
            double minLng = Double.MAX_VALUE, maxLng = -Double.MAX_VALUE;
            List<CommunityRouteResponse.PolylinePointDto> pts = new ArrayList<>();
            for (int i = 0; i < coords.length; i++) {
                double lat = coords[i].y, lng = coords[i].x;
                if (lat < minLat) minLat = lat;
                if (lat > maxLat) maxLat = lat;
                if (lng < minLng) minLng = lng;
                if (lng > maxLng) maxLng = lng;
                pts.add(CommunityRouteResponse.PolylinePointDto.builder()
                        .lat(lat).lng(lng).order(i + 1).build());
            }
            polylinePoints = pts;
            bounds = CommunityRouteResponse.BoundsDto.builder()
                    .northEast(CommunityRouteResponse.LatLngDto.builder().lat(maxLat).lng(maxLng).build())
                    .southWest(CommunityRouteResponse.LatLngDto.builder().lat(minLat).lng(minLng).build())
                    .build();
        }

        return CommunityRouteResponse.RouteDetailDto.builder()
                .routeId(route.getId())
                .routeName(route.getRouteName())
                .startPoint(startPoint)
                .endPoint(endPoint)
                .bounds(bounds)
                .polyline(polylinePoints)
                .checkpoints(List.of())
                .turnInstructions(List.of())
                .build();
    }

    private CommunityRouteResponse.CreatorDto toCreatorDto(User user) {
        if (user == null) return null;
        return CommunityRouteResponse.CreatorDto.builder()
                .userId(user.getId())
                .nickname(user.getNickname())
                .profileImageUrl(user.getProfileImageUrl())
                .build();
    }

    private String formatPace(int paceSecPerKm) {
        if (paceSecPerKm <= 0) return null;
        return String.format("%d'%02d\"", paceSecPerKm / 60, paceSecPerKm % 60);
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
