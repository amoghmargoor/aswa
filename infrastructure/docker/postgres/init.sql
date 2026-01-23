-- PostgreSQL initialization script for local development

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE aswa'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aswa')\gexec

-- Connect to the database
\c aswa

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE aswa TO aswa;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aswa;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aswa;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO aswa;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO aswa;

-- Log success
\echo 'Database initialization completed successfully'
