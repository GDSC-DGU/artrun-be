package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class LikeRouteResponse {
    private String communityRouteId;
    private boolean liked;
    private int likeCount;
}
