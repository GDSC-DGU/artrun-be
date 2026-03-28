package com.artrun.server.common;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum ErrorCode {

    // Common
    INVALID_INPUT(HttpStatus.BAD_REQUEST, "잘못된 입력값입니다."),
    INTERNAL_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "서버 내부 오류가 발생했습니다."),

    // Task
    TASK_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 작업을 찾을 수 없습니다."),
    TASK_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "작업 처리 중 오류가 발생했습니다."),

    // Route
    ROUTE_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 경로를 찾을 수 없습니다."),
    ROUTE_GENERATION_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "경로 생성에 실패했습니다."),

    // Session
    SESSION_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 세션을 찾을 수 없습니다."),

    // AI
    AI_API_ERROR(HttpStatus.SERVICE_UNAVAILABLE, "AI 서비스 호출에 실패했습니다."),

    // Map
    NO_NEARBY_NODE(HttpStatus.UNPROCESSABLE_ENTITY, "근처에 적합한 도로 노드를 찾을 수 없습니다."),
    ROUTING_FAILED(HttpStatus.UNPROCESSABLE_ENTITY, "경로 연결에 실패했습니다.");

    private final HttpStatus status;
    private final String message;
}
