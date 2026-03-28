package com.artrun.server.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class TrackRequest {

    @NotNull
    private Double lat;

    @NotNull
    private Double lng;

    private Long timestamp;
    private Double currentSpeed;
}
