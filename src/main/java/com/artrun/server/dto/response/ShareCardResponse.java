package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class ShareCardResponse {
    private String recordId;
    private String imageUrl;
    private LocalDateTime generatedAt;
}
