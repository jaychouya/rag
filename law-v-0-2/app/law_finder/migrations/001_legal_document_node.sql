CREATE TABLE IF NOT EXISTS legal_document_node (
    id BIGSERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES LegalDocuments (id) ON DELETE CASCADE,
    pathname TEXT NOT NULL,
    unit TEXT,
    node_index TEXT,
    summary TEXT,
    body TEXT,
    parent_id BIGINT REFERENCES legal_document_node (id) ON DELETE CASCADE,
    search_vector tsvector
);

CREATE INDEX IF NOT EXISTS idx_legal_document_node_document_id ON legal_document_node (document_id);
CREATE INDEX IF NOT EXISTS idx_legal_document_node_search_vector ON legal_document_node USING GIN (search_vector);
