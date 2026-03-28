package com.artrun.server;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@EnableAsync
@SpringBootApplication
public class ArtrunApplication {

	public static void main(String[] args) {
		SpringApplication.run(ArtrunApplication.class, args);
	}
}
