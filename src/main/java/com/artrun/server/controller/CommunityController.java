package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.PrepareRunRequest;
import com.artrun.server.dto.request.RegisterCommunityRouteRequest;
import com.artrun.server.dto.response.CommunityRouteResponse;
import com.artrun.server.dto.response.PrepareRunResponse;
import com.artrun.server.security.CustomUserDetails;
import com.artrun.server.service.CommunityService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@Tag(name = "Community", description = "커뮤니티 러닝 루트 API")
@RestController
@RequestMapping("/api/v1/community/routes")
@RequiredArgsConstructor
public class CommunityController {

    private final CommunityService communityService;

    @Operation(summary = "커뮤니티 루트 목록 조회 (비로그인 가능)")
    @GetMapping
    public ResponseEntity<ApiResponse<Page<CommunityRouteResponse>>> getRoutes(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PageableDefault(size = 10, sort = "createdAt", direction = Sort.Direction.DESC) Pageable pageable) {
        String userId = userDetails != null ? userDetails.getUserId() : null;
        return ResponseEntity.ok(ApiResponse.ok(communityService.getRoutes(userId, pageable)));
    }

    @Operation(summary = "커뮤니티 루트 상세 조회 (비로그인 가능)")
    @GetMapping("/{communityRouteId}")
    public ResponseEntity<ApiResponse<CommunityRouteResponse>> getRoute(
            @PathVariable String communityRouteId,
            @AuthenticationPrincipal CustomUserDetails userDetails) {
        String userId = userDetails != null ? userDetails.getUserId() : null;
        return ResponseEntity.ok(ApiResponse.ok(communityService.getRoute(communityRouteId, userId)));
    }

    @Operation(summary = "커뮤니티 루트 등록 (완주 기록만 가능)")
    @PostMapping
    public ResponseEntity<ApiResponse<CommunityRouteResponse>> register(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody RegisterCommunityRouteRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.ok("커뮤니티에 등록되었습니다.",
                        communityService.register(userDetails.getUserId(), request)));
    }

    @Operation(summary = "커뮤니티 루트 삭제 (본인만)")
    @DeleteMapping("/{communityRouteId}")
    public ResponseEntity<ApiResponse<Void>> delete(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String communityRouteId) {
        communityService.delete(userDetails.getUserId(), communityRouteId);
        return ResponseEntity.ok(ApiResponse.ok("삭제되었습니다.", null));
    }

    @Operation(summary = "커뮤니티 루트 좋아요")
    @PostMapping("/{communityRouteId}/like")
    public ResponseEntity<ApiResponse<Void>> like(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String communityRouteId) {
        communityService.like(userDetails.getUserId(), communityRouteId);
        return ResponseEntity.ok(ApiResponse.ok("좋아요 완료.", null));
    }

    @Operation(summary = "커뮤니티 루트 좋아요 취소")
    @DeleteMapping("/{communityRouteId}/like")
    public ResponseEntity<ApiResponse<Void>> unlike(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String communityRouteId) {
        communityService.unlike(userDetails.getUserId(), communityRouteId);
        return ResponseEntity.ok(ApiResponse.ok("좋아요 취소 완료.", null));
    }

    @Operation(summary = "커뮤니티 루트 실행 준비 (위치 검증)")
    @PostMapping("/{communityRouteId}/prepare-run")
    public ResponseEntity<ApiResponse<PrepareRunResponse>> prepareRun(
            @PathVariable String communityRouteId,
            @Valid @RequestBody PrepareRunRequest request) {
        return ResponseEntity.ok(ApiResponse.ok(communityService.prepareRun(communityRouteId, request)));
    }
}
