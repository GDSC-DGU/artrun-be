package com.artrun.server.dto.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class RegenerateRouteRequest {
    private String reason;
    private RouteGenerateRequest.PreferencesDto preferences;
}
