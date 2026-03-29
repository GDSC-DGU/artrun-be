package com.artrun.server.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class TrackRequest {

    @NotNull(message = "위도를 입력해주세요.")
    private Double lat;

    @NotNull(message = "경도를 입력해주세요.")
    private Double lng;

    private Long timestamp;
    private Double currentSpeed;
}
