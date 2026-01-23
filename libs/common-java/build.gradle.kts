/*
 * ASWA Common Java Library
 * Shared utilities, exceptions, and models for Java services
 */

plugins {
    `java-library`
}

dependencies {
    // API dependencies (exposed to consumers)
    api("org.slf4j:slf4j-api:${property("slf4jVersion")}")
    api("com.fasterxml.jackson.core:jackson-databind:${property("jacksonVersion")}")
    api("com.fasterxml.jackson.datatype:jackson-datatype-jsr310:${property("jacksonVersion")}")
    api("io.micrometer:micrometer-core:${property("micrometerVersion")}")

    // Implementation dependencies (internal only)
    implementation("com.github.ben-manes.caffeine:caffeine:${property("caffeineVersion")}")
    implementation("io.github.resilience4j:resilience4j-circuitbreaker:${property("resilience4jVersion")}")
    implementation("io.github.resilience4j:resilience4j-retry:${property("resilience4jVersion")}")
    implementation("io.github.resilience4j:resilience4j-ratelimiter:${property("resilience4jVersion")}")
    implementation("com.google.guava:guava:${property("guavaVersion")}")

    // JSpecify annotations
    compileOnly("org.jspecify:jspecify:0.3.0")

    // Test dependencies
    testImplementation("org.junit.jupiter:junit-jupiter:${property("junitVersion")}")
    testImplementation("org.junit.jupiter:junit-jupiter-params:${property("junitVersion")}")
    testImplementation("org.mockito:mockito-core:${property("mockitoVersion")}")
    testImplementation("org.mockito:mockito-junit-jupiter:${property("mockitoVersion")}")
    testImplementation("org.assertj:assertj-core:${property("assertjVersion")}")
    testImplementation("org.testcontainers:testcontainers:${property("testcontainersVersion")}")
    testImplementation("org.awaitility:awaitility:${property("awaitilityVersion")}")
}

tasks.test {
    useJUnitPlatform()
}

java {
    withJavadocJar()
    withSourcesJar()
}
