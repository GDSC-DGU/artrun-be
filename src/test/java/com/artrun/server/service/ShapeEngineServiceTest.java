package com.artrun.server.service;

import com.artrun.server.dto.AnchorPoint;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ShapeEngineServiceTest {

    private final ShapeEngineService service = new ShapeEngineService(
            "", "gemini-2.0-flash", new ObjectMapper());

    @Test
    @DisplayName("API Key 없으면 star stub 좌표를 반환한다")
    void generateShape_noApiKey_returnStubStar() {
        List<AnchorPoint> points = service.generateShapeCoordinates("star 3km", "star");

        assertThat(points).hasSizeGreaterThanOrEqualTo(10);
        assertThat(points.getFirst().getX()).isEqualTo(points.getLast().getX());
        assertThat(points.getFirst().getY()).isEqualTo(points.getLast().getY());
    }

    @Test
    @DisplayName("heart stub 좌표를 반환한다")
    void generateShape_noApiKey_returnStubHeart() {
        List<AnchorPoint> points = service.generateShapeCoordinates("heart 5km", "heart");

        assertThat(points).hasSizeGreaterThanOrEqualTo(10);
        assertThat(points.getFirst().getX()).isEqualTo(points.getLast().getX());
    }

    @Test
    @DisplayName("알 수 없는 shapeType이면 circle stub을 반환한다")
    void generateShape_unknownType_returnCircle() {
        List<AnchorPoint> points = service.generateShapeCoordinates("dog 3km", "dog");

        assertThat(points).hasSizeGreaterThanOrEqualTo(15);
        // circle: 모든 점이 원점에서 약 1.0 거리
        for (AnchorPoint p : points) {
            double dist = Math.sqrt(p.getX() * p.getX() + p.getY() * p.getY());
            assertThat(dist).isBetween(0.9, 1.1);
        }
    }
}
