package com.artrun.server.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;

@Repository
@RequiredArgsConstructor
public class OsmNodeRepository {

    private final JdbcTemplate jdbcTemplate;

    public Long findNearestNode(double lat, double lng, double radiusMeters) {
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

    public long getNodeCount() {
        return jdbcTemplate.queryForObject("SELECT count(*) FROM ways_vertices_pgr", Long.class);
    }

    public long getWayCount() {
        return jdbcTemplate.queryForObject("SELECT count(*) FROM ways", Long.class);
    }
}
