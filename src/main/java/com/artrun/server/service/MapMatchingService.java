package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class MapMatchingService {

    private static final double DEFAULT_RADIUS_METERS = 50.0;
    private static final double MAX_RADIUS_METERS = 200.0;
    private static final double RADIUS_INCREMENT = 50.0;

    private final JdbcTemplate jdbcTemplate;

    public List<Long> snapToOsmNodes(Coordinate[] coordinates) {
        log.info("Snapping {} coordinates to OSM nodes (radius={}m)", coordinates.length, DEFAULT_RADIUS_METERS);

        List<Long> nodeIds = new ArrayList<>();
        int failCount = 0;

        for (Coordinate coord : coordinates) {
            Long nodeId = findNearestPedestrianNode(coord.y, coord.x, DEFAULT_RADIUS_METERS);

            // 반경 확대 fallback
            if (nodeId == null) {
                nodeId = findWithExpandedRadius(coord.y, coord.x);
            }

            if (nodeId == null) {
                failCount++;
                log.warn("No OSM node found near ({}, {})", coord.y, coord.x);
                continue;
            }

            // 연속 중복 노드 방지
            if (nodeIds.isEmpty() || !nodeIds.getLast().equals(nodeId)) {
                nodeIds.add(nodeId);
            }
        }

        if (nodeIds.size() < 2) {
            throw new BusinessException(ErrorCode.NO_NEARBY_NODE,
                    "스냅된 노드가 2개 미만입니다. (%d/%d 실패)".formatted(failCount, coordinates.length));
        }

        log.info("Snapped to {} unique nodes ({} failures)", nodeIds.size(), failCount);
        return nodeIds;
    }

    private Long findNearestPedestrianNode(double lat, double lng, double radiusMeters) {
        String sql = """
                SELECT v.id
                FROM ways_vertices_pgr v
                JOIN ways w ON (v.id = w.source OR v.id = w.target)
                WHERE ST_DWithin(
                    v.the_geom::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography,
                    ?
                )
                AND w.tag_id IN (101, 102, 103, 104, 105, 106, 107, 108, 109, 110)
                ORDER BY ST_Distance(
                    v.the_geom::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography
                )
                LIMIT 1
                """;
        List<Map<String, Object>> results = jdbcTemplate.queryForList(
                sql, lng, lat, radiusMeters, lng, lat);

        if (results.isEmpty()) {
            // 보행자 도로가 없으면 모든 도로에서 검색
            return findNearestAnyNode(lat, lng, radiusMeters);
        }
        return ((Number) results.getFirst().get("id")).longValue();
    }

    private Long findNearestAnyNode(double lat, double lng, double radiusMeters) {
        String sql = """
                SELECT id FROM ways_vertices_pgr
                WHERE ST_DWithin(
                    the_geom::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography,
                    ?
                )
                ORDER BY ST_Distance(
                    the_geom::geography,
                    ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography
                )
                LIMIT 1
                """;
        List<Map<String, Object>> results = jdbcTemplate.queryForList(
                sql, lng, lat, radiusMeters, lng, lat);
        if (results.isEmpty()) return null;
        return ((Number) results.getFirst().get("id")).longValue();
    }

    private Long findWithExpandedRadius(double lat, double lng) {
        double radius = DEFAULT_RADIUS_METERS + RADIUS_INCREMENT;
        while (radius <= MAX_RADIUS_METERS) {
            Long nodeId = findNearestAnyNode(lat, lng, radius);
            if (nodeId != null) {
                log.debug("Found node at expanded radius {}m for ({}, {})", radius, lat, lng);
                return nodeId;
            }
            radius += RADIUS_INCREMENT;
        }
        return null;
    }
}
