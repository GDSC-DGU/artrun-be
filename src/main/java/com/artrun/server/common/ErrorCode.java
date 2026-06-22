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

    // Auth / User
    EMAIL_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 사용 중인 이메일입니다."),
    NICKNAME_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 사용 중인 닉네임입니다."),
    INVALID_CREDENTIALS(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다."),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, "유효하지 않은 토큰입니다."),
    USER_NOT_FOUND(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다."),
    OAUTH_FAILED(HttpStatus.BAD_GATEWAY, "소셜 로그인 처리에 실패했습니다."),

    // Session
    SESSION_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 세션을 찾을 수 없습니다."),
    SESSION_INACTIVE(HttpStatus.CONFLICT, "활성 상태의 세션이 아닙니다."),
    SESSION_NOT_FINISHED(HttpStatus.CONFLICT, "종료된 세션만 기록을 저장할 수 있습니다."),
    SESSION_ALREADY_ACTIVE(HttpStatus.CONFLICT, "이미 해당 경로로 진행 중인 세션이 있습니다."),
    SESSION_FORBIDDEN(HttpStatus.FORBIDDEN, "해당 세션에 대한 권한이 없습니다."),

    // Record
    RECORD_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 기록을 찾을 수 없습니다."),
    RECORD_FORBIDDEN(HttpStatus.FORBIDDEN, "해당 기록에 대한 권한이 없습니다."),
    RECORD_IN_COMMUNITY(HttpStatus.CONFLICT, "커뮤니티에 등록된 기록은 먼저 등록 해제가 필요합니다."),

    // Community
    COMMUNITY_ROUTE_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 커뮤니티 루트를 찾을 수 없습니다."),
    COMMUNITY_ROUTE_FORBIDDEN(HttpStatus.FORBIDDEN, "해당 커뮤니티 루트에 대한 권한이 없습니다."),
    COMMUNITY_ROUTE_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 커뮤니티에 등록된 기록입니다."),
    LIKE_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 좋아요한 루트입니다."),
    LIKE_NOT_FOUND(HttpStatus.NOT_FOUND, "좋아요 기록을 찾을 수 없습니다."),
    NOT_COMPLETED_RECORD(HttpStatus.BAD_REQUEST, "완주 기록만 커뮤니티에 등록할 수 있습니다."),

    // AI
    AI_API_ERROR(HttpStatus.SERVICE_UNAVAILABLE, "AI 서비스 호출에 실패했습니다."),

    // Map
    NO_NEARBY_NODE(HttpStatus.UNPROCESSABLE_ENTITY, "근처에 적합한 도로 노드를 찾을 수 없습니다."),
    ROUTING_FAILED(HttpStatus.UNPROCESSABLE_ENTITY, "경로 연결에 실패했습니다.");

    private final HttpStatus status;
    private final String message;
}
