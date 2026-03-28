package com.artrun.server.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
public class RecordResponse {
    private String recordId;
    private Double totalDistanceMeters;
    private Integer totalTimeSeconds;
    private Double averageSpeed;
    private String imageUrl;
}
