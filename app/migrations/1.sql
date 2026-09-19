ALTER TABLE note
ADD COLUMN tags hstore NOT NULL DEFAULT '';

ALTER TABLE note_comment
ADD COLUMN tags hstore;

-- Existing comments retain their original text. New comments keep hashtags in
-- their own tag snapshot, so the legacy full-text search must include both.
DROP INDEX note_comment_body_idx;

CREATE INDEX note_comment_body_idx ON note_comment USING gin (
    to_tsvector('simple', body || E'\n' || COALESCE(tags -> 'hashtags', ''))
)
WITH
    (fastupdate = FALSE);
