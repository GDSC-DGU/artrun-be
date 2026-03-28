package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.LineString;
import org.locationtech.jts.geom.PrecisionModel;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class RoutingEngineService {

    private static final GeometryFactory GEOMETRY_FACTORY = new GeometryFactory(new PrecisionModel(), 4326);

    private final JdbcTemplate jdbcTemplate;

    public LineString buildRoute(List<Long> nodeIds, boolean avoidMainRoad, boolean preferPark) {
        log.info("Building route through {} nodes", nodeIds.size());

        List<Coordinate> allCoords = new ArrayList<>();

        for (int i = 0; i < nodeIds.size() - 1; i++) {
            Long source = nodeIds.get(i);
            Long target = nodeIds.get(i + 1);

            List<Coordinate> segment = findShortestPath(source, target, avoidMainRoad, preferPark);
            if (segment.isEmpty()) {
                segment = findShortestPathFallback(source, target);
            }

            if (segment.isEmpty()) {
                log.warn("No path found between nodes {} and {}", source, target);
                continue;
            }

            // 이전 세그먼트의 마지막 좌표와 현재 세그먼트 첫 좌표 중복 제거
            if (!allCoords.isEmpty() && !segment.isEmpty()) {
                segment = segment.subList(1, segment.size());
            }
            allCoords.addAll(segment);
        }

        // 폐곡선으로 만들기: 마지막 노드 → 첫 노드 연결
        if (nodeIds.size() > 2) {
            Long lastNode = nodeIds.getLast();
            Long firstNode = nodeIds.getFirst();
            List<Coordinate> closingSegment = findShortestPath(lastNode, firstNode, avoidMainRoad, preferPark);
            if (closingSegment.isEmpty()) {
                closingSegment = findShortestPathFallback(lastNode, firstNode);
            }
            if (!closingSegment.isEmpty() && !allCoords.isEmpty()) {
                allCoords.addAll(closingSegment.subList(1, closingSegment.size()));
            }
        }

        if (allCoords.size() < 2) {
            throw new BusinessException(ErrorCode.ROUTING_FAILED, "경로를 구성할 수 없습니다.");
        }

        log.info("Route built with {} coordinates", allCoords.size());
        return GEOMETRY_FACTORY.createLineString(allCoords.toArray(new Coordinate[0]));
    }

    public double calculateRouteDistance(LineString route) {
        String sql = "SELECT ST_Length(ST_GeomFromText(?, 4326)::geography)";
        return jdbcTemplate.queryForObject(sql, Double.class, route.toText());
    }

    private List<Coordinate> findShortestPath(Long source, Long target, boolean avoidMainRoad, boolean preferPark) {
        String costColumn = buildCostExpression(avoidMainRoad, preferPark);

        String sql = """
                SELECT ST_X(v.the_geom) AS lng, ST_Y(v.the_geom) AS lat
                FROM pgr_dijkstra(
                    'SELECT gid AS id, source, target, %s AS cost, %s AS reverse_cost FROM ways',
                    ?, ?
                ) AS r
                JOIN ways_vertices_pgr v ON r.node = v.id
                WHERE r.node > 0
                ORDER BY r.seq
                """.formatted(costColumn, costColumn);

        return executePathQuery(sql, source, target);
    }

    private List<Coordinate> findShortestPathFallback(Long source, Long target) {
        String sql = """
                SELECT ST_X(v.the_geom) AS lng, ST_Y(v.the_geom) AS lat
                FROM pgr_dijkstra(
                    'SELECT gid AS id, source, target, cost, reverse_cost FROM ways',
                    ?, ?
                ) AS r
                JOIN ways_vertices_pgr v ON r.node = v.id
                WHERE r.node > 0
                ORDER BY r.seq
                """;
        return executePathQuery(sql, source, target);
    }

    private List<Coordinate> executePathQuery(String sql, Long source, Long target) {
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, source, target);
            return rows.stream()
                    .map(row -> new Coordinate(
                            ((Number) row.get("lng")).doubleValue(),
                            ((Number) row.get("lat")).doubleValue()))
                    .toList();
        } catch (Exception e) {
            log.debug("Path query failed between {} and {}: {}", source, target, e.getMessage());
            return List.of();
        }
    }

    private String buildCostExpression(boolean avoidMainRoad, boolean preferPark) {
        if (avoidMainRoad) {
            return "CASE WHEN tag_id IN (111, 112) THEN cost * 5.0 " +
                   "WHEN tag_id IN (101, 102, 103) THEN cost * 0.5 " +
                   "ELSE cost END";
        }
        return "cost";
    }
}
