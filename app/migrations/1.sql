ALTER TABLE note
ADD COLUMN tags hstore NOT NULL DEFAULT ''::hstore;

-- NULL means this comment did not change the tags. An empty hstore means the
-- author explicitly cleared them. Existing comments remain readable as text.
ALTER TABLE note_comment
ADD COLUMN tags hstore;

CREATE INDEX note_comment_legacy_tags_idx ON note_comment (note_id)
WHERE
    event = 'opened'
    AND tags IS NULL;

-- Keep legacy full-text search working after hashtags leave the body column.
DROP INDEX note_comment_body_idx;

CREATE INDEX note_comment_body_idx ON note_comment USING gin (
    to_tsvector(
        'simple',
        body || ' ' || coalesce(tags -> 'hashtags', '')
    )
)
WITH
    (fastupdate = FALSE);
