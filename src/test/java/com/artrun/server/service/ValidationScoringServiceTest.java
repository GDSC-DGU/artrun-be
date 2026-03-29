package com.artrun.server.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.LineString;
import org.locationtech.jts.geom.PrecisionModel;

import static org.assertj.core.api.Assertions.assertThat;

class ValidationScoringServiceTest {

    private ValidationScoringService service;
    private GeometryFactory gf;

    @BeforeEach
    void setUp() {
        service = new ValidationScoringService(null); // DB 관련 테스트는 제외
        gf = new GeometryFactory(new PrecisionModel(), 4326);
    }

    @Test
    @DisplayName("단순 라인은 유효한 경로로 판단한다")
    void validateRoute_simpleLine_returnsTrue() {
        LineString line = gf.createLineString(new Coordinate[]{
                new Coordinate(0, 0), new Coordinate(1, 1), new Coordinate(2, 0)
        });
        assertThat(service.validateRoute(line)).isTrue();
    }

    @Test
    @DisplayName("자기 교차 라인도 러닝 경로에서는 유효하다")
    void validateRoute_selfIntersecting_stillValid() {
        // 보타이 형태 (자기 교차)
        LineString line = gf.createLineString(new Coordinate[]{
                new Coordinate(0, 0), new Coordinate(2, 2),
                new Coordinate(2, 0), new Coordinate(0, 2)
        });
        assertThat(service.validateRoute(line)).isTrue();
    }

    @Test
    @DisplayName("compositeScore 가중 평균이 올바르게 계산된다")
    void calculateCompositeScore() {
        // similarity=80, pedestrian=60, distance=100
        // 80*0.5 + 60*0.3 + 100*0.2 = 40 + 18 + 20 = 78
        double score = service.calculateCompositeScore(80, 60, 100);
        assertThat(score).isEqualTo(78.0);
    }

    @Test
    @DisplayName("목표 거리와 동일하면 distanceAccuracy 100")
    void calculateDistanceAccuracy_exact() {
        assertThat(service.calculateDistanceAccuracy(5000, 5000)).isEqualTo(100.0);
    }

    @Test
    @DisplayName("목표 거리 대비 50% 벗어나면 0에 가깝다")
    void calculateDistanceAccuracy_farOff() {
        double accuracy = service.calculateDistanceAccuracy(7500, 5000);
        assertThat(accuracy).isEqualTo(0.0);
    }

    @Test
    @DisplayName("목표 거리가 0이면 100을 반환한다")
    void calculateDistanceAccuracy_zeroTarget() {
        assertThat(service.calculateDistanceAccuracy(1000, 0)).isEqualTo(100.0);
    }

    @Test
    @DisplayName("유사도 30 이상이면 최소 품질 충족")
    void meetsMinimumQuality_above() {
        assertThat(service.meetsMinimumQuality(30.0)).isTrue();
        assertThat(service.meetsMinimumQuality(50.0)).isTrue();
    }

    @Test
    @DisplayName("유사도 30 미만이면 최소 품질 미달")
    void meetsMinimumQuality_below() {
        assertThat(service.meetsMinimumQuality(29.9)).isFalse();
        assertThat(service.meetsMinimumQuality(0.0)).isFalse();
    }
}
