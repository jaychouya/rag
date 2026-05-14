CREATE TABLE IF NOT EXISTS petition_wiki_entry (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    triggers TEXT NOT NULL,
    actor TEXT,
    action TEXT,
    context TEXT,
    consequence TEXT,
    linked_document_ids INTEGER[] NOT NULL DEFAULT '{}',
    body TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_petition_wiki_slug ON petition_wiki_entry (slug);
CREATE INDEX IF NOT EXISTS idx_petition_wiki_doc_ids ON petition_wiki_entry USING GIN (linked_document_ids);
