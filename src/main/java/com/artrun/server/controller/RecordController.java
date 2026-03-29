package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.SaveRecordRequest;
import com.artrun.server.dto.response.RecordResponse;
import com.artrun.server.service.RecordService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "Record", description = "러닝 결과 저장 및 후처리 API")
@RestController
@RequestMapping("/api/v1/records")
@RequiredArgsConstructor
public class RecordController {

    private final RecordService recordService;

    @Operation(summary = "러닝 결과 저장", description = "운동 종료 후 전체 GPS 데이터를 전송하여 보정된 결과를 저장합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "저장 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "세션을 찾을 수 없음")
    })
    @PostMapping("/save")
    public ResponseEntity<ApiResponse<RecordResponse>> saveRecord(
            @Valid @RequestBody SaveRecordRequest request) {
        RecordResponse response = recordService.saveRecord(request);
        return ResponseEntity.ok(ApiResponse.ok("러닝 결과가 저장되었습니다.", response));
    }
}
