-- korean-stat-mcp - Optional PostgreSQL schema for full-text metadata search
-- Required only when DATABASE_URL is set. The KOSIS API search works without it.
--
-- Install Postgres extras: pip install korean-stat-mcp[postgres]
-- Initialize: psql ${DATABASE_URL} -f migrations/init.sql

-- Korean text-search config (simple tokenizer; works well for our metadata length)
DROP TEXT SEARCH CONFIGURATION IF EXISTS korean CASCADE;
CREATE TEXT SEARCH CONFIGURATION korean (COPY = simple);

-- Main metadata catalog
CREATE TABLE IF NOT EXISTS kosis_tables (
    id SERIAL PRIMARY KEY,

    tbl_id VARCHAR(50) UNIQUE NOT NULL,
    org_id VARCHAR(10) NOT NULL,
    stat_id VARCHAR(20),

    tbl_nm TEXT NOT NULL,
    org_nm VARCHAR(100),
    stat_nm TEXT,

    mt_atitle TEXT,
    contents TEXT,
    item03 TEXT,

    strt_prd_de VARCHAR(10),
    end_prd_de VARCHAR(10),
    prd_se VARCHAR(5),

    link_url TEXT,

    search_text TEXT,
    search_vector TSVECTOR,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE kosis_tables IS 'KOSIS metadata catalog for full-text search';
COMMENT ON COLUMN kosis_tables.search_text IS 'Combined text from tbl_nm, org_nm, contents, item03, mt_atitle';
COMMENT ON COLUMN kosis_tables.search_vector IS 'PostgreSQL tsvector for BM25-like FTS';

CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('korean', COALESCE(NEW.search_text, ''));
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_search_vector ON kosis_tables;
CREATE TRIGGER trg_update_search_vector
    BEFORE INSERT OR UPDATE OF search_text
    ON kosis_tables
    FOR EACH ROW
    EXECUTE FUNCTION update_search_vector();

-- Lightweight indexes; create the GIN index on search_vector after bulk load
CREATE INDEX IF NOT EXISTS idx_kosis_org_id ON kosis_tables(org_id);
CREATE INDEX IF NOT EXISTS idx_kosis_tbl_id ON kosis_tables(tbl_id);
CREATE INDEX IF NOT EXISTS idx_kosis_stat_id ON kosis_tables(stat_id);

-- Operational logging
CREATE TABLE IF NOT EXISTS data_load_logs (
    id SERIAL PRIMARY KEY,
    load_type VARCHAR(50) NOT NULL,
    records_processed INTEGER DEFAULT 0,
    records_success INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_messages JSONB,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds NUMERIC
);

COMMENT ON TABLE data_load_logs IS 'Tracks data loading operations for monitoring';

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO kosis;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO kosis;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO kosis;

INSERT INTO data_load_logs (load_type, records_success, completed_at)
VALUES ('schema_init', 1, NOW());
