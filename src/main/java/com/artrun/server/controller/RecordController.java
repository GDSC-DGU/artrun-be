package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.SaveRecordRequest;
import com.artrun.server.dto.request.ShareCardRequest;
import com.artrun.server.dto.response.RecordDetailResponse;
import com.artrun.server.dto.response.RecordResponse;
import com.artrun.server.dto.response.ShareCardResponse;
import com.artrun.server.security.CustomUserDetails;
import com.artrun.server.service.RecordService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;


@Tag(name = "Record", description = "러닝 기록 저장 및 조회 API")
@RestController
@RequestMapping("/api/v1/records")
@RequiredArgsConstructor
public class RecordController {

    private final RecordService recordService;

    @Operation(summary = "러닝 기록 저장 (FINISHED 상태 세션만 가능)")
    @PostMapping("/save")
    public ResponseEntity<ApiResponse<RecordResponse>> saveRecord(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody SaveRecordRequest request) {
        RecordResponse response = recordService.saveRecord(userDetails.getUserId(), request);
        return ResponseEntity.ok(ApiResponse.ok("러닝 기록이 저장되었습니다.", response));
    }

    @Operation(summary = "러닝 기록 상세 조회")
    @GetMapping("/{recordId}")
    public ResponseEntity<ApiResponse<RecordDetailResponse>> getRecord(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String recordId) {
        return ResponseEntity.ok(ApiResponse.ok("러닝 기록 상세 조회 성공", recordService.getRecord(userDetails.getUserId(), recordId)));
    }

    @Operation(summary = "SNS 공유 카드 재생성")
    @PostMapping("/{recordId}/share-card")
    public ResponseEntity<ApiResponse<ShareCardResponse>> regenerateShareCard(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String recordId,
            @RequestBody(required = false) ShareCardRequest request) {
        ShareCardResponse response = recordService.regenerateShareCard(
                userDetails.getUserId(), recordId, request != null ? request : new ShareCardRequest());
        return ResponseEntity.ok(ApiResponse.ok("SNS 공유 카드가 생성되었습니다.", response));
    }

    @Operation(summary = "러닝 기록 삭제 (커뮤니티 등록 시 불가)")
    @DeleteMapping("/{recordId}")
    public ResponseEntity<ApiResponse<Void>> deleteRecord(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String recordId) {
        recordService.deleteRecord(userDetails.getUserId(), recordId);
        return ResponseEntity.ok(ApiResponse.ok("러닝 기록이 삭제되었습니다.", null));
    }
}
