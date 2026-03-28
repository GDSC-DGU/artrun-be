package com.artrun.server.domain;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity @Table(name = "run_sessions")
@Getter @Setter @NoArgsConstructor(access = AccessLevel.PROTECTED) @Builder @AllArgsConstructor
public class RunSession {
    @Id @GeneratedValue(strategy = GenerationType.UUID) private String id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "route_id", nullable = false) private Route route;
    @Enumerated(EnumType.STRING) @Column(nullable = false) private SessionStatus status;
    private LocalDateTime startedAt; private LocalDateTime finishedAt;
    @Column(nullable = false, updatable = false) private LocalDateTime createdAt;
    @PrePersist protected void onCreate() { createdAt = LocalDateTime.now(); if (status == null) status = SessionStatus.ACTIVE; }
}
