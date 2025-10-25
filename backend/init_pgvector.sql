-- Initialize pgvector extension for PostgreSQL
-- This file is automatically executed on database initialization

-- Create pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is installed
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE funddb TO funduser;
