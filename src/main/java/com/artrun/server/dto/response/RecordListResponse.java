package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class RecordListResponse {
    private long totalCount;
    private List<RecordSummaryResponse> records;
}
