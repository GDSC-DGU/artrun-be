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
    private static final int MAX_COORDINATES_PER_REQUEST = 100;

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

    /**
     * 좌표열을 Mapbox Map Matching API로 도로에 매칭하여 경로를 반환한다.
     * 입력: 도형 윤곽을 따르는 촘촘한 좌표열 (lat/lng)
     * 출력: 도로를 따라가는 LineString
     */
    public LineString matchToRoads(Coordinate[] coordinates) {
        log.info("Mapbox Map Matching: {} coordinates", coordinates.length);

        List<Coordinate> allMatched = new ArrayList<>();

        // Mapbox는 한 번에 최대 100좌표 → 청크로 분할
        for (int start = 0; start < coordinates.length; start += MAX_COORDINATES_PER_REQUEST - 1) {
            int end = Math.min(start + MAX_COORDINATES_PER_REQUEST, coordinates.length);
            Coordinate[] chunk = new Coordinate[end - start];
            System.arraycopy(coordinates, start, chunk, 0, end - start);

            List<Coordinate> matched = callMapMatchingApi(chunk);

            if (!allMatched.isEmpty() && !matched.isEmpty()) {
                matched = matched.subList(1, matched.size());
            }
            allMatched.addAll(matched);
        }

        if (allMatched.size() < 2) {
            throw new BusinessException(ErrorCode.ROUTING_FAILED, "Mapbox Map Matching 실패: 매칭된 좌표가 부족합니다.");
        }

        log.info("Mapbox matched: {} -> {} coordinates", coordinates.length, allMatched.size());
        return GF.createLineString(allMatched.toArray(new Coordinate[0]));
    }

    private List<Coordinate> callMapMatchingApi(Coordinate[] coordinates) {
        // coordinates는 JTS 형식 (x=lng, y=lat)
        StringBuilder coordStr = new StringBuilder();
        StringBuilder radiuses = new StringBuilder();
        for (int i = 0; i < coordinates.length; i++) {
            if (i > 0) {
                coordStr.append(";");
                radiuses.append(";");
            }
            coordStr.append(coordinates[i].x).append(",").append(coordinates[i].y);
            radiuses.append("25"); // 25m 반경 내 도로 매칭
        }

        String url = "https://api.mapbox.com/matching/v5/mapbox/walking/%s?access_token=%s&geometries=geojson&radiuses=%s&overview=full"
                .formatted(coordStr, apiKey, radiuses);

        try {
            String response = restClient.get()
                    .uri(url)
                    .retrieve()
                    .body(String.class);

            JsonNode root = objectMapper.readTree(response);
            String code = root.path("code").asText();

            if (!"Ok".equals(code)) {
                log.warn("Mapbox Map Matching returned: {}", code);
                return List.of();
            }

            JsonNode matchings = root.path("matchings");
            if (matchings.isEmpty()) {
                return List.of();
            }

            // 첫 번째 매칭 결과의 geometry 좌표 추출
            JsonNode coords = matchings.path(0).path("geometry").path("coordinates");
            List<Coordinate> result = new ArrayList<>();
            for (JsonNode point : coords) {
                double lng = point.path(0).asDouble();
                double lat = point.path(1).asDouble();
                result.add(new Coordinate(lng, lat));
            }

            return result;
        } catch (Exception e) {
            log.error("Mapbox API call failed: {}", e.getMessage());
            return List.of();
        }
    }
}
