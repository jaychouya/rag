ALTER TABLE petition_wiki_entry
    ADD COLUMN IF NOT EXISTS effective_from DATE,
    ADD COLUMN IF NOT EXISTS repealed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_version TEXT;

CREATE INDEX IF NOT EXISTS idx_petition_wiki_repealed ON petition_wiki_entry (repealed);
