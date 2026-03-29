package com.artrun.server.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class StartSessionRequest {

    @NotBlank(message = "경로 ID를 입력해주세요.")
    private String routeId;
}
