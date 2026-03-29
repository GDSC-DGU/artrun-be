package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.LineString;
import org.locationtech.jts.geom.PrecisionModel;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
public class MapboxMapMatchingService {

    private static final GeometryFactory GF = new GeometryFactory(new PrecisionModel(), 4326);
    private static final int MAX_WAYPOINTS_PER_REQUEST = 25;

    private final String apiKey;
    private final ObjectMapper objectMapper;
    private final RestClient restClient;

    public MapboxMapMatchingService(
            @Value("${mapbox.api-key:}") String apiKey,
            ObjectMapper objectMapper) {
        this.apiKey = apiKey;
        this.objectMapper = objectMapper;
        this.restClient = RestClient.create();
    }

    public boolean isAvailable() {
        return apiKey != null && !apiKey.isBlank();
    }

    public LineString matchToRoads(Coordinate[] coordinates) {
        log.info("Mapbox Directions: {} input coordinates", coordinates.length);

        Coordinate[] waypoints = selectWaypoints(coordinates);
        log.info("Selected {} waypoints", waypoints.length);

        List<Coordinate> allCoords = new ArrayList<>();

        for (int start = 0; start < waypoints.length - 1; start += MAX_WAYPOINTS_PER_REQUEST - 1) {
            int end = Math.min(start + MAX_WAYPOINTS_PER_REQUEST, waypoints.length);
            Coordinate[] chunk = new Coordinate[end - start];
            System.arraycopy(waypoints, start, chunk, 0, end - start);

            List<Coordinate> segment = callDirectionsApi(chunk);
            if (segment.isEmpty()) continue;

            if (!allCoords.isEmpty()) {
                segment = segment.subList(1, segment.size());
            }
            allCoords.addAll(segment);
        }

        // 폐곡선: 마지막 → 첫 웨이포인트
        if (waypoints.length > 2) {
            List<Coordinate> closing = callDirectionsApi(
                    new Coordinate[]{waypoints[waypoints.length - 1], waypoints[0]});
            if (!closing.isEmpty() && !allCoords.isEmpty()) {
                allCoords.addAll(closing.subList(1, closing.size()));
            }
        }

        if (allCoords.size() < 2) {
            throw new BusinessException(ErrorCode.ROUTING_FAILED, "Mapbox 경로 생성 실패");
        }

        log.info("Mapbox route: {} coordinates", allCoords.size());
        return GF.createLineString(allCoords.toArray(new Coordinate[0]));
    }

    private Coordinate[] selectWaypoints(Coordinate[] coords) {
        int maxTotal = MAX_WAYPOINTS_PER_REQUEST * 2 - 1; // 49
        if (coords.length <= maxTotal) return coords;

        double step = (double) (coords.length - 1) / (maxTotal - 1);
        Coordinate[] selected = new Coordinate[maxTotal];
        for (int i = 0; i < maxTotal; i++) {
            selected[i] = coords[Math.min((int) Math.round(i * step), coords.length - 1)];
        }
        return selected;
    }

    private List<Coordinate> callDirectionsApi(Coordinate[] waypoints) {
        StringBuilder coordStr = new StringBuilder();
        for (int i = 0; i < waypoints.length; i++) {
            if (i > 0) coordStr.append(";");
            coordStr.append(waypoints[i].x).append(",").append(waypoints[i].y);
        }

        String url = "https://api.mapbox.com/directions/v5/mapbox/walking/%s?access_token=%s&geometries=geojson&overview=full&continue_straight=true"
                .formatted(coordStr, apiKey);

        try {
            String response = restClient.get().uri(url).retrieve().body(String.class);
            JsonNode root = objectMapper.readTree(response);

            if (!"Ok".equals(root.path("code").asText())) {
                log.warn("Mapbox: {}", root.path("message").asText());
                return List.of();
            }

            JsonNode routes = root.path("routes");
            if (routes.isEmpty()) return List.of();

            JsonNode coords = routes.path(0).path("geometry").path("coordinates");
            List<Coordinate> result = new ArrayList<>();
            for (JsonNode pt : coords) {
                result.add(new Coordinate(pt.path(0).asDouble(), pt.path(1).asDouble()));
            }
            return result;
        } catch (Exception e) {
            log.error("Mapbox API failed: {}", e.getMessage());
            return List.of();
        }
    }
}
