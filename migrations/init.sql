-- KOSIS MCP Server - Database Initialization
-- PostgreSQL 16 + pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create Korean text search configuration (simple, no morphological analysis)
-- This works well with vector search for semantic coverage
DROP TEXT SEARCH CONFIGURATION IF EXISTS korean CASCADE;
CREATE TEXT SEARCH CONFIGURATION korean (COPY = simple);

-- Main metadata catalog table
CREATE TABLE IF NOT EXISTS kosis_tables (
    id SERIAL PRIMARY KEY,

    -- KOSIS identifiers
    tbl_id VARCHAR(50) UNIQUE NOT NULL,
    org_id VARCHAR(10) NOT NULL,
    stat_id VARCHAR(20),

    -- Core metadata
    tbl_nm TEXT NOT NULL,                   -- Table name (테이블명)
    org_nm VARCHAR(100),                    -- Organization name (기관명)
    stat_nm TEXT,                           -- Statistics name (통계명)

    -- Additional descriptive fields
    mt_atitle TEXT,                         -- Category path (분류 경로)
    contents TEXT,                          -- Content description
    item03 TEXT,                            -- Additional description

    -- Period information
    strt_prd_de VARCHAR(10),                -- Start period
    end_prd_de VARCHAR(10),                 -- End period
    prd_se VARCHAR(5),                      -- Period type (Y/M/Q)

    -- URLs
    link_url TEXT,                          -- KOSIS direct link

    -- Search columns
    search_text TEXT,                       -- Combined text for search
    search_vector TSVECTOR,                 -- Full-text search vector (GIN)
    embedding VECTOR(1536),                 -- OpenAI embedding (HNSW)

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments for documentation
COMMENT ON TABLE kosis_tables IS 'KOSIS metadata catalog with 103K+ statistical tables';
COMMENT ON COLUMN kosis_tables.search_text IS 'Combined text from tbl_nm, org_nm, contents, item03, mt_atitle for search';
COMMENT ON COLUMN kosis_tables.search_vector IS 'PostgreSQL tsvector for BM25-like full-text search';
COMMENT ON COLUMN kosis_tables.embedding IS 'OpenAI text-embedding-3-small 1536-dim vector';

-- Function to update search_vector automatically
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('korean', COALESCE(NEW.search_text, ''));
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for auto-updating search_vector
DROP TRIGGER IF EXISTS trg_update_search_vector ON kosis_tables;
CREATE TRIGGER trg_update_search_vector
    BEFORE INSERT OR UPDATE OF search_text
    ON kosis_tables
    FOR EACH ROW
    EXECUTE FUNCTION update_search_vector();

-- Basic indexes (created immediately)
CREATE INDEX IF NOT EXISTS idx_kosis_org_id ON kosis_tables(org_id);
CREATE INDEX IF NOT EXISTS idx_kosis_tbl_id ON kosis_tables(tbl_id);
CREATE INDEX IF NOT EXISTS idx_kosis_stat_id ON kosis_tables(stat_id);

-- Note: Heavy indexes (GIN for search_vector, HNSW for embedding)
-- should be created AFTER data load for better performance.
-- See: scripts/create_indexes.sql

-- Data quality tracking table
CREATE TABLE IF NOT EXISTS data_load_logs (
    id SERIAL PRIMARY KEY,
    load_type VARCHAR(50) NOT NULL,         -- 'metadata', 'embeddings', 'incremental'
    records_processed INTEGER DEFAULT 0,
    records_success INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_messages JSONB,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds NUMERIC
);

COMMENT ON TABLE data_load_logs IS 'Tracks data loading operations for monitoring';

-- Stored procedure for hybrid search (will be used by Python)
-- This is a template - actual implementation handles weights in Python
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding VECTOR(1536),
    fts_weight FLOAT DEFAULT 0.5,
    vec_weight FLOAT DEFAULT 0.5,
    result_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    tbl_id VARCHAR(50),
    tbl_nm TEXT,
    org_nm VARCHAR(100),
    rrf_score FLOAT,
    fts_rank INTEGER,
    vec_rank INTEGER
) AS $$
WITH
-- Full-text search results
fts_results AS (
    SELECT
        kt.tbl_id,
        ROW_NUMBER() OVER (ORDER BY ts_rank(kt.search_vector, plainto_tsquery('korean', query_text)) DESC) AS fts_rank
    FROM kosis_tables kt
    WHERE kt.search_vector @@ plainto_tsquery('korean', query_text)
    LIMIT 100
),
-- Vector similarity search results
vec_results AS (
    SELECT
        kt.tbl_id,
        ROW_NUMBER() OVER (ORDER BY kt.embedding <=> query_embedding) AS vec_rank
    FROM kosis_tables kt
    WHERE kt.embedding IS NOT NULL
    ORDER BY kt.embedding <=> query_embedding
    LIMIT 100
),
-- RRF combination (k=60 is standard)
combined AS (
    SELECT
        COALESCE(f.tbl_id, v.tbl_id) AS tbl_id,
        f.fts_rank,
        v.vec_rank,
        COALESCE(fts_weight / (60 + f.fts_rank), 0) +
        COALESCE(vec_weight / (60 + v.vec_rank), 0) AS rrf_score
    FROM fts_results f
    FULL OUTER JOIN vec_results v ON f.tbl_id = v.tbl_id
)
SELECT
    c.tbl_id,
    kt.tbl_nm,
    kt.org_nm,
    c.rrf_score::FLOAT,
    COALESCE(c.fts_rank, 0)::INTEGER,
    COALESCE(c.vec_rank, 0)::INTEGER
FROM combined c
JOIN kosis_tables kt ON c.tbl_id = kt.tbl_id
ORDER BY c.rrf_score DESC
LIMIT result_limit;
$$ LANGUAGE SQL STABLE;

COMMENT ON FUNCTION hybrid_search IS 'Hybrid search combining BM25 FTS and vector similarity with RRF fusion';

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO kosis;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO kosis;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO kosis;

-- Log successful initialization
INSERT INTO data_load_logs (load_type, records_success, completed_at)
VALUES ('schema_init', 1, NOW());
