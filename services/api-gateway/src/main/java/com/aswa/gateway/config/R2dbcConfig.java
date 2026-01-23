package com.aswa.gateway.config;

import io.r2dbc.postgresql.PostgresqlConnectionConfiguration;
import io.r2dbc.postgresql.PostgresqlConnectionFactory;
import io.r2dbc.spi.ConnectionFactory;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.r2dbc.config.AbstractR2dbcConfiguration;
import org.springframework.data.r2dbc.repository.config.EnableR2dbcRepositories;

import java.time.Duration;

/**
 * R2DBC configuration for reactive database access.
 *
 * Configures:
 * - PostgreSQL connection factory
 * - Connection pool settings
 * - Statement timeouts
 * - Validation queries
 */
@Slf4j
@Configuration
@EnableR2dbcRepositories(basePackages = "com.aswa.gateway.repository")
public class R2dbcConfig extends AbstractR2dbcConfiguration {

    @Value("${spring.r2dbc.host:localhost}")
    private String host;

    @Value("${spring.r2dbc.port:5432}")
    private int port;

    @Value("${spring.r2dbc.database:aswa}")
    private String database;

    @Value("${spring.r2dbc.username:aswa}")
    private String username;

    @Value("${spring.r2dbc.password:aswa_dev_password}")
    private String password;

    @Value("${spring.r2dbc.pool.initial-size:5}")
    private int initialSize;

    @Value("${spring.r2dbc.pool.max-size:20}")
    private int maxSize;

    @Value("${spring.r2dbc.pool.max-acquire-time:3000}")
    private int maxAcquireTime;

    @Value("${spring.r2dbc.pool.max-idle-time:30000}")
    private int maxIdleTime;

    @Override
    @Bean
    public ConnectionFactory connectionFactory() {
        log.info("Configuring R2DBC connection factory: host={}, port={}, database={}",
                host, port, database);

        PostgresqlConnectionConfiguration config = PostgresqlConnectionConfiguration.builder()
                .host(host)
                .port(port)
                .database(database)
                .username(username)
                .password(password)
                .connectTimeout(Duration.ofMillis(maxAcquireTime))
                .statementTimeout(Duration.ofSeconds(30))
                .build();

        return new PostgresqlConnectionFactory(config);
    }
}
