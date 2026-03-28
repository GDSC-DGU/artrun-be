package com.artrun.server.domain;

import jakarta.persistence.*;
import lombok.*;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.geom.LineString;
import java.time.LocalDateTime;

@Entity @Table(name = "routes")
@Getter @Setter @NoArgsConstructor(access = AccessLevel.PROTECTED) @Builder @AllArgsConstructor
public class Route {
    @Id @GeneratedValue(strategy = GenerationType.UUID) private String id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "task_id") private RouteTask task;
    @Column(columnDefinition = "geometry(LineString, 4326)") private LineString polyline;
    @Column(columnDefinition = "geometry(Geometry, 4326)") private Geometry originalShape;
    private Double distanceMeters;
    private Double similarityScore;
    private Double pedestrianRoadRatio;
    private Integer ranking;
    @Column(nullable = false, updatable = false) private LocalDateTime createdAt;
    @PrePersist protected void onCreate() { createdAt = LocalDateTime.now(); }
}
