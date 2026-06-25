package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.PrepareRunRequest;
import com.artrun.server.dto.request.RegisterCommunityRouteRequest;
import com.artrun.server.dto.response.CommunityRouteListResponse;
import com.artrun.server.dto.response.CommunityRouteResponse;
import com.artrun.server.dto.response.LikeRouteResponse;
import com.artrun.server.dto.response.PrepareRunResponse;
import com.artrun.server.dto.response.RegisterCommunityRouteResponse;
import com.artrun.server.security.CustomUserDetails;
import com.artrun.server.service.CommunityService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
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
    public ResponseEntity<ApiResponse<CommunityRouteListResponse>> getRoutes(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "ALL") String filter,
            @RequestParam(defaultValue = "RECENT_DESC") String sort,
            @RequestParam(required = false) Double lat,
            @RequestParam(required = false) Double lng,
            @RequestParam(defaultValue = "5") Double radiusKm,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size) {
        String userId = userDetails != null ? userDetails.getUserId() : null;
        return ResponseEntity.ok(ApiResponse.ok("커뮤니티 루트 목록 조회 성공",
                communityService.getRoutes(userId, keyword, filter, sort, lat, lng, radiusKm, page, size)));
    }

    @Operation(summary = "커뮤니티 루트 상세 조회 (비로그인 가능)")
    @GetMapping("/{communityRouteId}")
    public ResponseEntity<ApiResponse<CommunityRouteResponse>> getRoute(
            @PathVariable String communityRouteId,
            @AuthenticationPrincipal CustomUserDetails userDetails) {
        String userId = userDetails != null ? userDetails.getUserId() : null;
        return ResponseEntity.ok(ApiResponse.ok("커뮤니티 루트 상세 조회 성공",
                communityService.getRoute(communityRouteId, userId)));
    }

    @Operation(summary = "커뮤니티 루트 등록 (완주 기록만 가능)")
    @PostMapping
    public ResponseEntity<ApiResponse<RegisterCommunityRouteResponse>> register(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody RegisterCommunityRouteRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.ok("커뮤니티에 러닝 루트가 등록되었습니다.",
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
    public ResponseEntity<ApiResponse<LikeRouteResponse>> like(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String communityRouteId) {
        return ResponseEntity.ok(ApiResponse.ok("좋아요를 눌렀습니다.",
                communityService.like(userDetails.getUserId(), communityRouteId)));
    }

    @Operation(summary = "커뮤니티 루트 좋아요 취소")
    @DeleteMapping("/{communityRouteId}/like")
    public ResponseEntity<ApiResponse<LikeRouteResponse>> unlike(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String communityRouteId) {
        return ResponseEntity.ok(ApiResponse.ok("좋아요를 취소했습니다.",
                communityService.unlike(userDetails.getUserId(), communityRouteId)));
    }

    @Operation(summary = "커뮤니티 루트 실행 준비 (위치 검증)")
    @PostMapping("/{communityRouteId}/prepare-run")
    public ResponseEntity<ApiResponse<PrepareRunResponse>> prepareRun(
            @PathVariable String communityRouteId,
            @Valid @RequestBody PrepareRunRequest request) {
        return ResponseEntity.ok(ApiResponse.ok("커뮤니티 루트 실행 준비 완료",
                communityService.prepareRun(communityRouteId, request)));
    }
}
