# Multi-stage build for Java API Gateway
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app

# Copy Gradle wrapper and build files
COPY gradlew .
COPY gradle gradle
COPY gradle.properties .
COPY build.gradle.kts settings.gradle.kts ./

# Copy shared libraries
COPY libs libs

# Copy service source
COPY services/api-gateway services/api-gateway

# Build the application
RUN ./gradlew :services:api-gateway:bootJar --no-daemon

# Runtime stage
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -S aswa && adduser -S aswa -G aswa

# Copy built JAR from builder
COPY --from=builder /app/services/api-gateway/build/libs/*.jar app.jar

# Switch to non-root user
USER aswa

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s \
    CMD wget -q --spider http://localhost:8080/actuator/health || exit 1

# JVM tuning for containers
ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-XX:+UseG1GC", \
    "-XX:+UseStringDeduplication", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", \
    "app.jar"]
