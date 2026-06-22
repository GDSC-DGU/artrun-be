package com.artrun.server.domain;

public enum SessionStatus {
    ACTIVE,     // 러닝 중
    PAUSED,     // 일시정지
    FINISHED,   // 종료 완료 (기록 저장 대기)
    COMPLETED,  // 기록 저장 완료
    CANCELLED   // 취소됨
}
