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
    private static final double[] BBOX_MARGINS = {0.02, 0.05, 0.1};

    private final JdbcTemplate jdbcTemplate;

    public LineString buildRoute(List<Long> nodeIds, boolean avoidMainRoad, boolean preferPark) {
        log.info("Building route through {} nodes via A*", nodeIds.size());

        double[] bbox = getBoundingBox(nodeIds);
        List<Coordinate> allCoords = new ArrayList<>();

        for (int i = 0; i < nodeIds.size() - 1; i++) {
            Long source = nodeIds.get(i);
            Long target = nodeIds.get(i + 1);

            List<Coordinate> segment = findPathWithExpandingBbox(source, target, avoidMainRoad, bbox);

            if (segment.isEmpty()) {
                log.warn("No road path found between nodes {} and {}, skipping", source, target);
                continue;
            }

            if (!allCoords.isEmpty() && !segment.isEmpty()) {
                segment = segment.subList(1, segment.size());
            }
            allCoords.addAll(segment);
        }

        // 폐곡선: 마지막 → 첫 노드
        if (nodeIds.size() > 2) {
            List<Coordinate> closing = findPathWithExpandingBbox(
                    nodeIds.getLast(), nodeIds.getFirst(), avoidMainRoad, bbox);
            if (!closing.isEmpty() && !allCoords.isEmpty()) {
                allCoords.addAll(closing.subList(1, closing.size()));
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

    private List<Coordinate> findPathWithExpandingBbox(Long source, Long target,
                                                       boolean avoidMainRoad, double[] baseBbox) {
        for (double margin : BBOX_MARGINS) {
            double[] expanded = {
                    baseBbox[0] - margin, baseBbox[1] - margin,
                    baseBbox[2] + margin, baseBbox[3] + margin
            };

            // A* 시도
            List<Coordinate> result = findAStarPath(source, target, avoidMainRoad, expanded);
            if (!result.isEmpty()) return result;

            // A* 실패 시 Dijkstra 폴백 (코스트 없이)
            result = findDijkstraPath(source, target, expanded);
            if (!result.isEmpty()) return result;
        }
        return List.of();
    }

    private List<Coordinate> findAStarPath(Long source, Long target, boolean avoidMainRoad, double[] bbox) {
        String costExpr = buildCostExpression(avoidMainRoad);
        String bboxFilter = bboxWhere(bbox);

        // pgr_aStar는 x1,y1,x2,y2 컬럼 필요 (휴리스틱용)
        String innerSql = ("SELECT gid AS id, source, target, " +
                "%s AS cost, %s AS reverse_cost, x1, y1, x2, y2 FROM ways WHERE %s")
                .formatted(costExpr, costExpr, bboxFilter);

        String sql = """
                SELECT ST_X(v.the_geom) AS lng, ST_Y(v.the_geom) AS lat
                FROM pgr_aStar('%s', ?, ?) AS r
                JOIN ways_vertices_pgr v ON r.node = v.id
                WHERE r.node > 0
                ORDER BY r.seq
                """.formatted(innerSql.replace("'", "''"));

        return executeQuery(sql, source, target);
    }

    private List<Coordinate> findDijkstraPath(Long source, Long target, double[] bbox) {
        String innerSql = "SELECT gid AS id, source, target, cost, reverse_cost FROM ways WHERE %s"
                .formatted(bboxWhere(bbox));

        String sql = """
                SELECT ST_X(v.the_geom) AS lng, ST_Y(v.the_geom) AS lat
                FROM pgr_dijkstra('%s', ?, ?) AS r
                JOIN ways_vertices_pgr v ON r.node = v.id
                WHERE r.node > 0
                ORDER BY r.seq
                """.formatted(innerSql.replace("'", "''"));

        return executeQuery(sql, source, target);
    }

    private double[] getBoundingBox(List<Long> nodeIds) {
        String ids = nodeIds.stream().map(String::valueOf).reduce((a, b) -> a + "," + b).orElse("0");
        String sql = "SELECT ST_XMin(ST_Extent(the_geom)) as xmin, ST_YMin(ST_Extent(the_geom)) as ymin, " +
                     "ST_XMax(ST_Extent(the_geom)) as xmax, ST_YMax(ST_Extent(the_geom)) as ymax " +
                     "FROM ways_vertices_pgr WHERE id IN (" + ids + ")";
        Map<String, Object> row = jdbcTemplate.queryForMap(sql);
        return new double[]{
                ((Number) row.get("xmin")).doubleValue(),
                ((Number) row.get("ymin")).doubleValue(),
                ((Number) row.get("xmax")).doubleValue(),
                ((Number) row.get("ymax")).doubleValue()
        };
    }

    private String bboxWhere(double[] bbox) {
        return "the_geom && ST_MakeEnvelope(%f,%f,%f,%f,4326)".formatted(bbox[0], bbox[1], bbox[2], bbox[3]);
    }

    private List<Coordinate> executeQuery(String sql, Long source, Long target) {
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

    private String buildCostExpression(boolean avoidMainRoad) {
        if (avoidMainRoad) {
            return "CASE WHEN tag_id IN (111, 112) THEN cost * 5.0 " +
                   "WHEN tag_id IN (101, 102, 103) THEN cost * 0.5 " +
                   "ELSE cost END";
        }
        return "cost";
    }
}
