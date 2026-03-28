package com.artrun.server.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.geom.LineString;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class ValidationScoringService {

    private static final double MIN_SIMILARITY_THRESHOLD = 30.0;

    private final JdbcTemplate jdbcTemplate;

    public boolean validateRoute(LineString routePolyline) {
        // Self-intersection 검사
        boolean isSimple = routePolyline.isSimple();
        if (!isSimple) {
            log.warn("Route has self-intersections");
        }
        return true; // 러닝 경로는 교차해도 유효할 수 있음
    }

    public double calculateSimilarity(LineString routePolyline, Geometry originalShape) {
        String sql = """
                SELECT (1.0 - (
                    ST_HausdorffDistance(
                        ST_GeomFromText(?, 4326),
                        ST_GeomFromText(?, 4326)
                    ) / GREATEST(
                        ST_Length(ST_GeomFromText(?, 4326)::geography),
                        0.001
                    )
                )) * 100.0 AS similarity
                """;

        try {
            Double similarity = jdbcTemplate.queryForObject(sql, Double.class,
                    routePolyline.toText(),
                    originalShape.toText(),
                    routePolyline.toText());

            double score = Math.max(0, Math.min(100, similarity != null ? similarity : 0));
            log.info("Similarity score: {}", score);
            return score;
        } catch (Exception e) {
            log.error("Similarity calculation failed", e);
            return 0.0;
        }
    }

    public double calculatePedestrianRoadRatio(LineString routePolyline) {
        String sql = """
                WITH route_buffer AS (
                    SELECT ST_Buffer(ST_GeomFromText(?, 4326)::geography, 10)::geometry AS geom
                ),
                total_ways AS (
                    SELECT COALESCE(SUM(ST_Length(w.the_geom::geography)), 0) AS total_length
                    FROM ways w, route_buffer rb
                    WHERE ST_Intersects(w.the_geom, rb.geom)
                ),
                pedestrian_ways AS (
                    SELECT COALESCE(SUM(ST_Length(w.the_geom::geography)), 0) AS ped_length
                    FROM ways w, route_buffer rb
                    WHERE ST_Intersects(w.the_geom, rb.geom)
                    AND w.tag_id IN (101, 102, 103, 104, 105, 106, 107, 108)
                )
                SELECT CASE WHEN tw.total_length > 0
                    THEN (pw.ped_length / tw.total_length) * 100.0
                    ELSE 0 END AS ratio
                FROM total_ways tw, pedestrian_ways pw
                """;

        try {
            Double ratio = jdbcTemplate.queryForObject(sql, Double.class, routePolyline.toText());
            return ratio != null ? ratio : 0.0;
        } catch (Exception e) {
            log.error("Pedestrian road ratio calculation failed", e);
            return 0.0;
        }
    }

    public double calculateCompositeScore(double similarityScore, double pedestrianRatio, double distanceAccuracy) {
        // 가중 평균: 유사도 50%, 보행자도로 비율 30%, 거리 정확도 20%
        return similarityScore * 0.5 + pedestrianRatio * 0.3 + distanceAccuracy * 0.2;
    }

    public double calculateDistanceAccuracy(double actualDistance, double targetDistance) {
        if (targetDistance <= 0) return 100.0;
        double ratio = actualDistance / targetDistance;
        // 목표 거리 대비 ±20% 이내이면 만점에 가까움
        double accuracy = Math.max(0, 100.0 - Math.abs(1.0 - ratio) * 200.0);
        return Math.min(100.0, accuracy);
    }

    public boolean meetsMinimumQuality(double similarityScore) {
        return similarityScore >= MIN_SIMILARITY_THRESHOLD;
    }
}
