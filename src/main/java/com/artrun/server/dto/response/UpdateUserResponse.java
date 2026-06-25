package com.artrun.server.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class UpdateUserResponse {
    private String userId;
    private String nickname;
    private String profileImageUrl;
    private LocalDateTime updatedAt;
}
