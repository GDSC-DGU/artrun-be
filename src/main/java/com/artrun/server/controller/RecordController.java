package com.artrun.server.controller;

import com.artrun.server.common.ApiResponse;
import com.artrun.server.dto.request.SaveRecordRequest;
import com.artrun.server.dto.response.RecordResponse;
import com.artrun.server.service.RecordService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/records")
@RequiredArgsConstructor
public class RecordController {

    private final RecordService recordService;

    @PostMapping("/save")
    public ResponseEntity<ApiResponse<RecordResponse>> saveRecord(
            @Valid @RequestBody SaveRecordRequest request) {
        RecordResponse response = recordService.saveRecord(request);
        return ResponseEntity.ok(ApiResponse.ok("러닝 결과가 저장되었습니다.", response));
    }
}
