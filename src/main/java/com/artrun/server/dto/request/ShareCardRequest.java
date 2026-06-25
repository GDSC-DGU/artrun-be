package com.artrun.server.dto.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class ShareCardRequest {
    private String theme;
    private boolean includeMap;
    private boolean includeStats;
}
