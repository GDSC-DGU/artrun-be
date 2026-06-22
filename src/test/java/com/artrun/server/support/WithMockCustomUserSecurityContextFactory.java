package com.artrun.server.support;

import com.artrun.server.domain.AuthProvider;
import com.artrun.server.domain.User;
import com.artrun.server.security.CustomUserDetails;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.test.context.support.WithSecurityContextFactory;

public class WithMockCustomUserSecurityContextFactory
        implements WithSecurityContextFactory<WithMockCustomUser> {

    @Override
    public SecurityContext createSecurityContext(WithMockCustomUser annotation) {
        User user = User.builder()
                .id(annotation.userId())
                .email(annotation.email())
                .nickname(annotation.nickname())
                .provider(AuthProvider.EMAIL)
                .build();

        CustomUserDetails userDetails = new CustomUserDetails(user);
        var auth = new UsernamePasswordAuthenticationToken(
                userDetails, null, userDetails.getAuthorities());

        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(auth);
        return context;
    }
}
