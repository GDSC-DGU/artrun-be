package com.artrun.server.domain;

import jakarta.persistence.*;
import lombok.*;
import org.locationtech.jts.geom.LineString;
import java.time.LocalDateTime;

@Entity @Table(name = "run_records")
@Getter @Setter @NoArgsConstructor(access = AccessLevel.PROTECTED) @Builder @AllArgsConstructor
public class RunRecord {
    @Id @GeneratedValue(strategy = GenerationType.UUID) private String id;
    @OneToOne(fetch = FetchType.LAZY) @JoinColumn(name = "session_id", nullable = false, unique = true) private RunSession session;
    @Column(columnDefinition = "geometry(LineString, 4326)") private LineString rawPolyline;
    @Column(columnDefinition = "geometry(LineString, 4326)") private LineString correctedPolyline;
    private Double totalDistanceMeters; private Integer totalTimeSeconds; private Double averageSpeed; private String imageUrl;
    @Column(nullable = false, updatable = false) private LocalDateTime createdAt;
    @PrePersist protected void onCreate() { createdAt = LocalDateTime.now(); }
}
