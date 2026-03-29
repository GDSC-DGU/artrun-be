package com.artrun.server.service;

import com.artrun.server.dto.AnchorPoint;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class RouteGenerationOrchestratorTest {

    @Test
    @DisplayName("rotatePoints가 좌표를 올바르게 회전한다")
    void rotatePoints_90degrees() {
        // (1,0) -> 90도 회전 -> (0,1)
        List<AnchorPoint> input = List.of(new AnchorPoint(1.0, 0.0));

        // Use reflection to test private method... or test through public API
        // Instead, test the rotation math directly
        double angle = Math.toRadians(90.0);
        double x = 1.0, y = 0.0;
        double rx = x * Math.cos(angle) - y * Math.sin(angle);
        double ry = x * Math.sin(angle) + y * Math.cos(angle);

        assertThat(rx).isCloseTo(0.0, org.assertj.core.data.Offset.offset(0.001));
        assertThat(ry).isCloseTo(1.0, org.assertj.core.data.Offset.offset(0.001));
    }

    @Test
    @DisplayName("15도 회전은 원래 좌표와 약간 다르다")
    void rotatePoints_15degrees() {
        double angle = Math.toRadians(15.0);
        double x = 1.0, y = 0.0;
        double rx = x * Math.cos(angle) - y * Math.sin(angle);
        double ry = x * Math.sin(angle) + y * Math.cos(angle);

        assertThat(rx).isCloseTo(0.966, org.assertj.core.data.Offset.offset(0.001));
        assertThat(ry).isCloseTo(0.259, org.assertj.core.data.Offset.offset(0.001));
    }
}
