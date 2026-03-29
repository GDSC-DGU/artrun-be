package com.artrun.server.service;

import com.artrun.server.dto.AnchorPoint;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.geom.LineString;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

class GeospatialScaleServiceTest {

    private GeospatialScaleService service;

    @BeforeEach
    void setUp() {
        service = new GeospatialScaleService();
    }

    @Test
    @DisplayName("정규화 좌표를 실제 위경도로 변환한다")
    void scaleAndTranslate_convertsNormalizedToLatLng() {
        List<AnchorPoint> points = List.of(
                new AnchorPoint(0.0, 1.0),
                new AnchorPoint(1.0, 0.0),
                new AnchorPoint(0.0, -1.0),
                new AnchorPoint(-1.0, 0.0),
                new AnchorPoint(0.0, 1.0)
        );

        Coordinate[] result = service.scaleAndTranslate(points, 37.5665, 126.9780, 5.0);

        assertThat(result).hasSize(5);
        // 모든 좌표가 서울 근처여야 함
        for (Coordinate c : result) {
            assertThat(c.y).isBetween(37.0, 38.0);
            assertThat(c.x).isBetween(126.0, 128.0);
        }
    }

    @Test
    @DisplayName("스케일링 결과 중심점 근처에 분포한다")
    void scaleAndTranslate_centeredAroundStartPoint() {
        List<AnchorPoint> points = List.of(
                new AnchorPoint(0.0, 0.5),
                new AnchorPoint(0.5, 0.0),
                new AnchorPoint(0.0, -0.5),
                new AnchorPoint(-0.5, 0.0),
                new AnchorPoint(0.0, 0.5)
        );

        Coordinate[] result = service.scaleAndTranslate(points, 37.5665, 126.9780, 2.0);

        double avgLat = 0, avgLng = 0;
        for (Coordinate c : result) {
            avgLat += c.y;
            avgLng += c.x;
        }
        avgLat /= result.length;
        avgLng /= result.length;

        assertThat(avgLat).isCloseTo(37.5665, within(0.05));
        assertThat(avgLng).isCloseTo(126.9780, within(0.05));
    }

    @Test
    @DisplayName("4개 이상 닫힌 좌표로 Polygon을 생성한다")
    void createGeometry_polygon() {
        Coordinate[] coords = new Coordinate[]{
                new Coordinate(0, 0), new Coordinate(1, 0),
                new Coordinate(1, 1), new Coordinate(0, 1),
                new Coordinate(0, 0)
        };

        Geometry geom = service.createGeometry(coords);
        assertThat(geom.getGeometryType()).isEqualTo("Polygon");
    }

    @Test
    @DisplayName("3개 미만 좌표로 LineString을 생성한다")
    void createGeometry_lineString() {
        Coordinate[] coords = new Coordinate[]{
                new Coordinate(0, 0), new Coordinate(1, 1)
        };

        Geometry geom = service.createGeometry(coords);
        assertThat(geom.getGeometryType()).isEqualTo("LineString");
    }

    @Test
    @DisplayName("닫히지 않은 좌표를 자동으로 닫아 Polygon을 생성한다")
    void createGeometry_autoCloses() {
        Coordinate[] coords = new Coordinate[]{
                new Coordinate(0, 0), new Coordinate(1, 0),
                new Coordinate(1, 1), new Coordinate(0, 1)
        };

        Geometry geom = service.createGeometry(coords);
        assertThat(geom.getGeometryType()).isEqualTo("Polygon");
    }

    @Test
    @DisplayName("createPoint가 올바른 SRID 4326 포인트를 생성한다")
    void createPoint() {
        var point = service.createPoint(37.5665, 126.9780);
        assertThat(point.getY()).isEqualTo(37.5665);
        assertThat(point.getX()).isEqualTo(126.9780);
        assertThat(point.getSRID()).isEqualTo(4326);
    }

    @Test
    @DisplayName("perimeter가 0인 경우 예외를 던진다")
    void scaleAndTranslate_zeroPerimeter_throws() {
        List<AnchorPoint> points = List.of(
                new AnchorPoint(0.0, 0.0),
                new AnchorPoint(0.0, 0.0),
                new AnchorPoint(0.0, 0.0)
        );

        assertThatThrownBy(() -> service.scaleAndTranslate(points, 37.5665, 126.9780, 5.0))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
