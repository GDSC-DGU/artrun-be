package com.artrun.server.service;

import com.artrun.server.dto.AnchorPoint;
import lombok.extern.slf4j.Slf4j;
import org.locationtech.jts.geom.*;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
public class GeospatialScaleService {

    private static final double EARTH_RADIUS_METERS = 6_371_000.0;
    private static final GeometryFactory GEOMETRY_FACTORY = new GeometryFactory(new PrecisionModel(), 4326);

    public Coordinate[] scaleAndTranslate(List<AnchorPoint> anchorPoints, double lat, double lng, double targetDistanceKm) {
        log.info("Scaling {} anchor points to {}km at ({}, {})", anchorPoints.size(), targetDistanceKm, lat, lng);

        double currentPerimeter = calculatePerimeter(anchorPoints);
        if (currentPerimeter == 0) {
            throw new IllegalArgumentException("Perimeter is zero, cannot scale.");
        }

        double targetPerimeterMeters = targetDistanceKm * 1000.0;
        double scaleFactor = targetPerimeterMeters / currentPerimeter;

        // 위도에 따른 경도 보정 계수
        double latRadians = Math.toRadians(lat);
        double metersPerDegreeLat = (Math.PI / 180.0) * EARTH_RADIUS_METERS;
        double metersPerDegreeLng = metersPerDegreeLat * Math.cos(latRadians);

        Coordinate[] coords = new Coordinate[anchorPoints.size()];
        for (int i = 0; i < anchorPoints.size(); i++) {
            AnchorPoint p = anchorPoints.get(i);

            // 정규화 좌표를 미터 단위로 스케일링 후 위경도 오프셋으로 변환
            double offsetMetersX = p.getX() * scaleFactor;
            double offsetMetersY = p.getY() * scaleFactor;

            double offsetLng = offsetMetersX / metersPerDegreeLng;
            double offsetLat = offsetMetersY / metersPerDegreeLat;

            coords[i] = new Coordinate(lng + offsetLng, lat + offsetLat);
        }

        log.info("Scaled coordinates: perimeter={}m (target={}m)", calculatePerimeterMeters(coords), targetPerimeterMeters);
        return coords;
    }

    public Geometry createGeometry(Coordinate[] coordinates) {
        if (coordinates.length < 4) {
            return GEOMETRY_FACTORY.createLineString(coordinates);
        }
        // 폐곡선인지 확인하고, 아니면 닫아줌
        if (!coordinates[0].equals2D(coordinates[coordinates.length - 1])) {
            Coordinate[] closed = new Coordinate[coordinates.length + 1];
            System.arraycopy(coordinates, 0, closed, 0, coordinates.length);
            closed[coordinates.length] = new Coordinate(coordinates[0]);
            coordinates = closed;
        }
        return GEOMETRY_FACTORY.createPolygon(coordinates);
    }

    public LineString createLineString(Coordinate[] coordinates) {
        return GEOMETRY_FACTORY.createLineString(coordinates);
    }

    public Point createPoint(double lat, double lng) {
        return GEOMETRY_FACTORY.createPoint(new Coordinate(lng, lat));
    }

    /**
     * 앵커 포인트 사이에 중간 보간점을 삽입하여 도형 윤곽을 촘촘하게 만든다.
     * 포인트 간 간격이 maxSpacingMeters 이하가 될 때까지 분할.
     */
    public Coordinate[] interpolate(Coordinate[] coords, double maxSpacingMeters) {
        List<Coordinate> result = new ArrayList<>();
        for (int i = 0; i < coords.length - 1; i++) {
            result.add(coords[i]);
            double dist = haversineDistance(coords[i].y, coords[i].x, coords[i + 1].y, coords[i + 1].x);
            int segments = Math.max(1, (int) Math.ceil(dist / maxSpacingMeters));
            for (int s = 1; s < segments; s++) {
                double t = (double) s / segments;
                double lng = coords[i].x + t * (coords[i + 1].x - coords[i].x);
                double lat = coords[i].y + t * (coords[i + 1].y - coords[i].y);
                result.add(new Coordinate(lng, lat));
            }
        }
        result.add(coords[coords.length - 1]);
        log.info("Interpolated {} -> {} points (maxSpacing={}m)", coords.length, result.size(), maxSpacingMeters);
        return result.toArray(new Coordinate[0]);
    }

    private double calculatePerimeter(List<AnchorPoint> points) {
        double perimeter = 0;
        for (int i = 0; i < points.size() - 1; i++) {
            double dx = points.get(i + 1).getX() - points.get(i).getX();
            double dy = points.get(i + 1).getY() - points.get(i).getY();
            perimeter += Math.sqrt(dx * dx + dy * dy);
        }
        return perimeter;
    }

    private double calculatePerimeterMeters(Coordinate[] coords) {
        double perimeter = 0;
        for (int i = 0; i < coords.length - 1; i++) {
            perimeter += haversineDistance(coords[i].y, coords[i].x, coords[i + 1].y, coords[i + 1].x);
        }
        return perimeter;
    }

    private double haversineDistance(double lat1, double lng1, double lat2, double lng2) {
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return EARTH_RADIUS_METERS * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }
}
