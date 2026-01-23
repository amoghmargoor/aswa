# PostgreSQL with custom initialization
FROM postgres:16-alpine

# Install additional extensions
RUN apk add --no-cache postgresql-contrib

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql

# Set default environment
ENV POSTGRES_DB=aswa \
    POSTGRES_USER=aswa \
    POSTGRES_PASSWORD=aswa_dev_password

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s \
    CMD pg_isready -U aswa -d aswa || exit 1
