package com.artrun.server.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResumeSessionRequest {

    @NotNull(message = "현재 위치를 입력해주세요.")
    @Valid
    private StartSessionRequest.CurrentPointDto currentPoint;
}
