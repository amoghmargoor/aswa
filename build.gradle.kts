/*
 * ASWA - AI-driven insight aggregation platform
 * Root Build Configuration (Kotlin DSL)
 */

plugins {
    java
    jacoco
    id("com.diffplug.spotless")
}

// Configure Java toolchain for all projects
java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

allprojects {
    group = "com.aswa"
    version = "0.1.0"

    repositories {
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "java")
    apply(plugin = "jacoco")
    apply(plugin = "com.diffplug.spotless")

    dependencies {
        // Common logging
        implementation("org.slf4j:slf4j-api:${property("slf4jVersion")}")
        implementation("ch.qos.logback:logback-classic:${property("logbackVersion")}")
        implementation("ch.qos.logback:logback-core:${property("logbackVersion")}")

        // Observability
        implementation("io.micrometer:micrometer-core:${property("micrometerVersion")}")
        implementation("io.micrometer:micrometer-registry-prometheus:${property("micrometerVersion")}")

        // JSON logging
        implementation("net.logstash.logback:logstash-logback-encoder:${property("logstashEncoderVersion")}")

        // Test dependencies
        testImplementation("org.junit.jupiter:junit-jupiter:${property("junitVersion")}")
        testImplementation("org.junit.jupiter:junit-jupiter-params:${property("junitVersion")}")
        testImplementation("org.mockito:mockito-core:${property("mockitoVersion")}")
        testImplementation("org.mockito:mockito-junit-jupiter:${property("mockitoVersion")}")
        testImplementation("org.assertj:assertj-core:${property("assertjVersion")}")
    }

    tasks.withType<Test> {
        useJUnitPlatform()

        testLogging {
            events("passed", "skipped", "failed")
            showStandardStreams = false
        }

        // Enable parallel test execution
        maxParallelForks = (Runtime.getRuntime().availableProcessors() / 2).takeIf { it > 0 } ?: 1

        finalizedBy(tasks.jacocoTestReport)
    }

    // JaCoCo configuration
    tasks.jacocoTestReport {
        dependsOn(tasks.test)

        reports {
            xml.required.set(true)
            html.required.set(true)
        }
    }

    tasks.register("jacocoTestCoverageVerification", JacocoReport::class) {
        dependsOn(tasks.test)

        violationRules {
            rule {
                limit {
                    minimum = "0.80".toBigDecimal()
                }
            }
        }
    }

    // Spotless configuration - Google Java Format
    spotless {
        java {
            googleJavaFormat("1.19.1")
            removeUnusedImports()
            trimTrailingWhitespace()
            endWithNewline()

            targetExclude("**/build/**", "**/generated/**")
        }
    }

    // Error Prone static analysis
    tasks.withType<JavaCompile> {
        options.compilerArgs.addAll(listOf(
            "-Xlint:unchecked",
            "-Xlint:deprecation"
        ))
    }
}

// Custom tasks for root project

tasks.register("checkAll") {
    group = "verification"
    description = "Run all verification tasks across all projects"

    dependsOn(subprojects.map { it.tasks.named("check") })
}

tasks.register("testAll") {
    group = "verification"
    description = "Run all tests across all projects"

    dependsOn(subprojects.map { it.tasks.named("test") })
}

tasks.register("cleanAll") {
    group = "build"
    description = "Clean all build artifacts across all projects"

    dependsOn(subprojects.map { it.tasks.named("clean") })
}

tasks.register("formatAll") {
    group = "formatting"
    description = "Format all code across all projects"

    dependsOn(subprojects.map { it.tasks.named("spotlessApply") })
}

tasks.register("lintAll") {
    group = "verification"
    description = "Check code formatting across all projects"

    dependsOn(subprojects.map { it.tasks.named("spotlessCheck") })
}

// Aggregate JaCoCo report
tasks.register<JacocoReport>("jacocoRootReport") {
    group = "verification"
    description = "Generate aggregate code coverage report"

    dependsOn(subprojects.map { it.tasks.named("test") })

    additionalSourceDirs.setFrom(subprojects.map { it.sourceSets.main.get().allSource.srcDirs })
    sourceDirectories.setFrom(subprojects.map { it.sourceSets.main.get().allSource.srcDirs })
    classDirectories.setFrom(subprojects.map { it.sourceSets.main.get().output })
    executionData.setFrom(
        subprojects.map { it.tasks.named<JacocoReport>("jacocoTestReport").get().executionData }
    )

    reports {
        xml.required.set(true)
        html.required.set(true)
        csv.required.set(false)
    }
}

// Helper to access source sets
val Project.sourceSets: SourceSetContainer
    get() = extensions.getByType()
