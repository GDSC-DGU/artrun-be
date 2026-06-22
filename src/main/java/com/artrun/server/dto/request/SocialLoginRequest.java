package com.artrun.server.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class SocialLoginRequest {

    @NotBlank(message = "provider를 입력해주세요. (KAKAO, GOOGLE)")
    private String provider;

    @NotBlank(message = "소셜 액세스 토큰을 입력해주세요.")
    private String token;
}
