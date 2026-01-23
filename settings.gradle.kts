/*
 * ASWA - AI-driven insight aggregation platform
 * Gradle Settings (Kotlin DSL)
 */

pluginManagement {
    val springBootVersion: String by settings
    val kotlinVersion: String by settings
    val spotlessVersion: String by settings

    plugins {
        id("org.springframework.boot") version springBootVersion apply false
        id("io.spring.dependency-management") version "1.1.4" apply false
        kotlin("jvm") version kotlinVersion apply false
        kotlin("plugin.spring") version kotlinVersion apply false
        id("com.diffplug.spotless") version spotlessVersion apply false
    }

    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.8.0"
}

rootProject.name = "aswa"

// Enable type-safe project accessors
enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")

// Shared libraries
include("libs:common-java")

// Java services
include("services:api-gateway")
include("services:notification-service")
include("services:integration-service")

// Configure project directories
project(":libs:common-java").projectDir = file("libs/common-java")
project(":services:api-gateway").projectDir = file("services/api-gateway")
project(":services:notification-service").projectDir = file("services/notification-service")
project(":services:integration-service").projectDir = file("services/integration-service")
