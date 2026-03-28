package com.artrun.server.domain;

import jakarta.persistence.*;
import lombok.*;
import org.locationtech.jts.geom.Point;
import java.time.LocalDateTime;

@Entity @Table(name = "route_tasks")
@Getter @Setter @NoArgsConstructor(access = AccessLevel.PROTECTED) @Builder @AllArgsConstructor
public class RouteTask {
    @Id @GeneratedValue(strategy = GenerationType.UUID) private String id;
    @Enumerated(EnumType.STRING) @Column(nullable = false) private TaskStatus status;
    private String requestText;
    private String shapeType;
    private String activityType;
    private Double targetDistanceKm;
    @Column(columnDefinition = "geometry(Point, 4326)") private Point startPoint;
    private Boolean avoidMainRoad;
    private Boolean preferPark;
    private String errorMessage;
    @Column(nullable = false, updatable = false) private LocalDateTime createdAt;
    private LocalDateTime completedAt;
    @PrePersist protected void onCreate() { createdAt = LocalDateTime.now(); if (status == null) status = TaskStatus.PENDING; }
}
