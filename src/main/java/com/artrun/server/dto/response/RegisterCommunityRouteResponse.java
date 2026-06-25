package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class RegisterCommunityRouteResponse {
    private String communityRouteId;
    private String recordId;
    private String routeId;
    private String title;
    private String visibility;
    private LocalDateTime createdAt;
}
