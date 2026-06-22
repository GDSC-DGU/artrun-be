package com.artrun.server.repository;

import com.artrun.server.domain.AuthProvider;
import com.artrun.server.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, String> {
    Optional<User> findByEmail(String email);
    Optional<User> findByProviderAndSocialId(AuthProvider provider, String socialId);
    boolean existsByEmail(String email);
    boolean existsByNickname(String nickname);
}
