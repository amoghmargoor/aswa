-- ASWA PostgreSQL Initialization Script
-- This script runs when the PostgreSQL container is first created
-- It sets up the database, user, and grants necessary permissions

-- Create ASWA database user
CREATE USER aswa WITH PASSWORD 'aswa_dev_password';

-- Create ASWA database
CREATE DATABASE aswa OWNER aswa;

-- Grant all privileges on the database to the aswa user
GRANT ALL PRIVILEGES ON DATABASE aswa TO aswa;

-- Connect to the aswa database to set additional permissions
\c aswa

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO aswa;

-- Grant default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO aswa;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO aswa;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO aswa;

-- Enable necessary extensions (these will be created by migrations, but we set permissions here)
-- The aswa user needs permission to create extensions if migrations require them
ALTER USER aswa WITH SUPERUSER;  -- Required for creating extensions like uuid-ossp, pg_trgm

-- Note: In production, use a more restricted approach:
-- 1. Have a separate migration user with SUPERUSER
-- 2. Run migrations as migration user
-- 3. Use aswa user only for application runtime with restricted permissions
-- 4. Grant only necessary table/sequence/function permissions to aswa

-- Create a comment
COMMENT ON DATABASE aswa IS 'ASWA AI-driven insight aggregation platform database';

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'ASWA database initialized successfully';
    RAISE NOTICE 'Database: aswa';
    RAISE NOTICE 'User: aswa';
    RAISE NOTICE 'Next step: Run migrations using ./scripts/db-migrate.sh';
END $$;
