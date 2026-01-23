package com.aswa.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.r2dbc.repository.config.EnableR2dbcRepositories;

/**
 * ASWA API Gateway - Main entry point for the reactive API Gateway service.
 *
 * This service provides:
 * - JWT-based authentication and authorization
 * - Tenant-scoped data access
 * - RESTful APIs for all ASWA entities
 * - WebFlux reactive programming model
 * - R2DBC reactive database access
 */
@SpringBootApplication
@EnableR2dbcRepositories
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
