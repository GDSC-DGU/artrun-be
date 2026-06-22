package com.artrun.server.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class PrepareRunRequest {

    @NotNull(message = "현재 위도를 입력해주세요.")
    private Double lat;

    @NotNull(message = "현재 경도를 입력해주세요.")
    private Double lng;
}
