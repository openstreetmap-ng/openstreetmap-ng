# Backfill legacy note hashtags

`MigrationService.backfill_note_hashtags` is an optional administrative task for
the structured note-tag rollout. It uses the same extractor as API 0.6 writes.
It does not run automatically at application startup.

## Deployment sequence

1. Back up the database and pause note creation, comments and replication/import
   writers. Keep writes paused until the backfill is complete.
2. **Before deploying migration `1.sql`**, record this inclusive legacy boundary:

   ```sql
   SELECT COALESCE(MAX(id), 0) FROM note_comment;
   ```

   Keep this value with the deployment record. Never replace it with a later
   maximum: new structured-tag comments may intentionally contain literal
   hashtags that must not be extracted. If a deployment has already accepted
   new writes and its original boundary is unknown, recover a verified boundary
   from the deployment backup before using this task.
3. Deploy the schema and application. The task is available on the admin tasks
   page as `backfill_note_hashtags`. Set `before_comment_id` to the recorded value,
   `start_note_id=1`, `batch_size=100`, and `dry_run=True` for a preview.
4. Inspect the logged counts, then run the same batch with `dry_run=False`.
   Each batch commits atomically. After a successful batch, use its logged
   `next_note_id` as the next `start_note_id`. A `None` cursor means completion.
   An exact full batch can require one final empty batch to confirm completion.
5. If interrupted, repeat the last uncertain batch with the **same boundary**.
   Existing snapshots are preserved; repeated runs do not duplicate extracted
   hashtags. A dry-run cursor is only a preview and must not advance the write
   cursor. Verify representative historical API responses before resuming writes.

The task locks each note in the same order as normal note writes. It changes
only the comment body, tag snapshot and rich-text cache reference, and the note's
current tags. IDs, authors, events and timestamps stay unchanged; no notification
emails are sent. PostgreSQL updates the existing full-text index automatically.
Existing newer explicit snapshots, including clears, remain authoritative.

Unsupported or oversized hashtags stay in the original text. URL fragments stay
untouched. Consecutive comments with identical hashtags retain their original
body rather than adding an unchanged snapshot, matching the live write path.
API 0.6 reconstructs extracted hashtags from each comment's own snapshot; their
placement and whitespace can be normalized, as with newly submitted comments.
