package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.UpdateUserRequest;
import com.artrun.server.dto.response.*;
import com.artrun.server.security.CustomUserDetails;
import com.artrun.server.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@Tag(name = "User", description = "사용자/마이페이지 API")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "내 정보 조회")
    @GetMapping("/me")
    public ResponseEntity<ApiResponse<UserResponse>> getMe(
            @AuthenticationPrincipal CustomUserDetails userDetails) {
        return ResponseEntity.ok(ApiResponse.ok(userService.getMe(userDetails.getUserId())));
    }

    @Operation(summary = "내 정보 수정")
    @PatchMapping("/me")
    public ResponseEntity<ApiResponse<UserResponse>> updateMe(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody UpdateUserRequest request) {
        return ResponseEntity.ok(ApiResponse.ok("정보가 수정되었습니다.",
                userService.updateMe(userDetails.getUserId(), request)));
    }

    @Operation(summary = "마이페이지 요약 조회")
    @GetMapping("/me/summary")
    public ResponseEntity<ApiResponse<MyPageSummaryResponse>> getSummary(
            @AuthenticationPrincipal CustomUserDetails userDetails) {
        return ResponseEntity.ok(ApiResponse.ok(userService.getSummary(userDetails.getUserId())));
    }

    @Operation(summary = "내 완주 기록 목록 조회")
    @GetMapping("/me/records")
    public ResponseEntity<ApiResponse<Page<RecordDetailResponse>>> getMyRecords(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PageableDefault(size = 10, sort = "createdAt", direction = Sort.Direction.DESC) Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.ok(userService.getMyRecords(userDetails.getUserId(), pageable)));
    }

    @Operation(summary = "내 완주 기록 상세 조회")
    @GetMapping("/me/records/{recordId}")
    public ResponseEntity<ApiResponse<RecordDetailResponse>> getMyRecord(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String recordId) {
        return ResponseEntity.ok(ApiResponse.ok(userService.getMyRecord(userDetails.getUserId(), recordId)));
    }

    @Operation(summary = "내 완주 기록 삭제")
    @DeleteMapping("/me/records/{recordId}")
    public ResponseEntity<ApiResponse<Void>> deleteMyRecord(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String recordId) {
        userService.deleteMyRecord(userDetails.getUserId(), recordId);
        return ResponseEntity.ok(ApiResponse.ok("기록이 삭제되었습니다.", null));
    }

    @Operation(summary = "좋아요한 러닝 루트 목록 조회")
    @GetMapping("/me/liked-routes")
    public ResponseEntity<ApiResponse<Page<CommunityRouteResponse>>> getLikedRoutes(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PageableDefault(size = 10) Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.ok(userService.getLikedRoutes(userDetails.getUserId(), pageable)));
    }

    @Operation(summary = "내가 커뮤니티에 등록한 루트 목록 조회")
    @GetMapping("/me/shared-routes")
    public ResponseEntity<ApiResponse<Page<CommunityRouteResponse>>> getMySharedRoutes(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PageableDefault(size = 10) Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.ok(userService.getMySharedRoutes(userDetails.getUserId(), pageable)));
    }
}
