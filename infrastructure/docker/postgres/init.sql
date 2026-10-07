-- =============================================================================
-- PostgreSQL Database Initialization Script
-- =============================================================================
-- This script runs once when the PostgreSQL container is first created.
-- It sets up the database, extensions, and initial schema elements that
-- must exist before Alembic migrations run.
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector (for RAG/vector search support - Step 9)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable btree_gin for composite GIN indexes
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- =============================================================================
-- Logging
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE 'Database initialization complete.';
    RAISE NOTICE 'Extensions: uuid-ossp, vector, pg_trgm, btree_gin';
    RAISE NOTICE 'Run Alembic migrations to create application tables.';
END $$;

