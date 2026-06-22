package com.artrun.server.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class RegisterCommunityRouteRequest {

    @NotBlank(message = "기록 ID를 입력해주세요.")
    private String recordId;

    @NotBlank(message = "제목을 입력해주세요.")
    @Size(max = 100, message = "제목은 100자 이하로 입력해주세요.")
    private String title;

    @Size(max = 500, message = "설명은 500자 이하로 입력해주세요.")
    private String description;
}
