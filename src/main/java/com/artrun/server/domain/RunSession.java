package com.artrun.server.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "run_sessions")
@Getter
@Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Builder
@AllArgsConstructor
public class RunSession {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "route_id", nullable = false)
    private Route route;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private SessionStatus status;

    private LocalDateTime startedAt;
    private LocalDateTime pausedAt;
    private LocalDateTime resumedAt;
    private LocalDateTime finishedAt;
    private LocalDateTime canceledAt;
    private String cancelReason;
    private Integer lastCompletionRate;
    private Integer lastDistanceTraveledMeters;
    private Integer lastDistanceRemainingMeters;
    private LocalDateTime lastTrackedAt;
    private Integer targetPaceSecPerKm;
    private Boolean voiceGuideEnabled;
    private Boolean edmControlEnabled;
    private Integer totalTimeSeconds;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        if (status == null) status = SessionStatus.ACTIVE;
    }
}
