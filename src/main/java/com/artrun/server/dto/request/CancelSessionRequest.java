package com.artrun.server.dto.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class CancelSessionRequest {
    private String reason;
}
